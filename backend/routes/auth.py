"""
Yahoo OAuth authentication routes.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database.connection import get_db
from app.database.models import User, OAuthToken, AuthCode
from app.services.yahoo_api import YahooAPIService

router = APIRouter()

# JWT configuration
JWT_SECRET_KEY = settings.APP_SECRET_KEY
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 7  # 1 week

# Authorization code configuration
AUTH_CODE_EXPIRE_SECONDS = 60  # 1 minute - very short-lived

# Security scheme for Bearer token
bearer_scheme = HTTPBearer(auto_error=False)


def cleanup_expired_codes(db: Session) -> None:
    """Remove expired authorization codes from database."""
    db.query(AuthCode).filter(AuthCode.expires_at < datetime.now(timezone.utc)).delete()
    db.commit()


def create_auth_code(db: Session, user_id: int) -> str:
    """
    Create a short-lived, single-use authorization code.

    This code can be exchanged for a JWT token via the /exchange endpoint.
    """
    # Clean up old codes first
    cleanup_expired_codes(db)

    code = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=AUTH_CODE_EXPIRE_SECONDS)

    auth_code = AuthCode(
        code=code,
        user_id=user_id,
        expires_at=expires_at,
    )
    db.add(auth_code)
    db.commit()

    return code


def consume_auth_code(db: Session, code: str) -> Optional[int]:
    """
    Validate and consume an authorization code.

    Returns the user_id if valid, None otherwise.
    The code is invalidated after this call (single-use).
    """
    auth_code = db.query(AuthCode).filter(
        AuthCode.code == code,
        AuthCode.used == False,  # noqa: E712
    ).first()

    if not auth_code:
        return None

    # Check expiration
    expires = auth_code.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    if expires < datetime.now(timezone.utc):
        # Expired - mark as used and return None
        auth_code.used = True
        db.commit()
        return None

    # Mark as used (single-use)
    auth_code.used = True
    db.commit()

    return auth_code.user_id


def create_access_token(user_id: int) -> str:
    """Create a JWT access token for the user."""
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[int]:
    """
    Verify a JWT token and return the user ID.

    Returns:
        User ID if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return int(user_id)
    except JWTError:
        return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[User]:
    """
    Get the current logged-in user from session or Bearer token.

    Supports both:
    - Session-based auth (cookies) for direct browser access
    - Bearer token auth for Streamlit/API clients

    Returns:
        User if logged in, None otherwise
    """
    user_id = None

    # First, try Bearer token (for Streamlit/API clients)
    if credentials:
        user_id = verify_token(credentials.credentials)

    # Fallback to session-based auth (for direct browser access)
    if not user_id:
        user_id = request.session.get("user_id")

    if not user_id:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    return user


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    """
    Initiate Yahoo OAuth login flow.

    Generates a state token for CSRF protection, stores it in session,
    and redirects user to Yahoo authorization page.
    """
    # Generate CSRF state token
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    # Generate authorization URL
    auth_url = YahooAPIService.get_authorization_url(state=state)

    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    Handle Yahoo OAuth callback.

    Exchanges authorization code for tokens, fetches user info,
    creates/updates user in database, and establishes session.
    """
    # Handle OAuth errors
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth error: {error} - {error_description}",
        )

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    # Verify state to prevent CSRF
    stored_state = request.session.get("oauth_state")
    if not stored_state or stored_state != state:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Clear used state
    del request.session["oauth_state"]

    # Exchange code for tokens
    yahoo_service = YahooAPIService(db=db)
    try:
        token_data = await yahoo_service.exchange_code_for_token(code)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to exchange code for token: {str(e)}",
        )

    # Get Yahoo user GUID from token response or API
    yahoo_guid = token_data.get("xoauth_yahoo_guid")

    if not yahoo_guid:
        # Fetch user info from Yahoo API using the new token
        try:
            from app.parsing.helpers import safe_get
            import httpx

            headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1",
                    headers=headers,
                    params={"format": "json"},
                )
                response.raise_for_status()
                user_data = response.json()

            # Extract GUID from response
            yahoo_guid = safe_get(
                user_data, "fantasy_content", "users", "0", "user", 0, "guid"
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch user info from Yahoo: {str(e)}",
            )

    if not yahoo_guid:
        raise HTTPException(
            status_code=400,
            detail="Could not get Yahoo user identifier",
        )

    # Find or create user
    user = db.query(User).filter(User.yahoo_guid == yahoo_guid).first()

    if not user:
        # Create new user
        user = User(yahoo_guid=yahoo_guid)
        db.add(user)
        db.commit()
        db.refresh(user)

    # Save/update OAuth token
    yahoo_service.user = user
    yahoo_service._save_token(token_data)

    # Set session (for direct browser access to FastAPI)
    request.session["user_id"] = user.id

    # Generate short-lived auth code for Streamlit (more secure than JWT in URL)
    auth_code = create_auth_code(db, user.id)

    # Redirect to frontend with auth code in URL
    redirect_url = f"{settings.FRONTEND_URL}?{urlencode({'code': auth_code})}"
    return RedirectResponse(url=redirect_url)


@router.get("/logout")
async def logout(request: Request) -> dict:
    """
    Log out the current user.

    Clears the session but keeps tokens in database for potential reuse.
    """
    request.session.clear()
    return {"status": "ok", "message": "Logged out successfully"}


@router.post("/exchange")
async def exchange_code_for_token(
    code: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Exchange a short-lived authorization code for a JWT access token.

    This endpoint is called by Streamlit after the OAuth redirect.
    The authorization code is single-use and expires after 60 seconds.

    Args:
        code: The authorization code from the OAuth redirect

    Returns:
        access_token: JWT token for API authentication
        token_type: Always "bearer"

    Raises:
        401: If the code is invalid, expired, or already used
    """
    user_id = consume_auth_code(db, code)

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authorization code",
        )

    # Generate JWT access token
    access_token = create_access_token(user_id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.get("/me")
async def get_current_user_info(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Get current user information.

    Returns user info if logged in, error if not.
    """
    user = get_current_user(request, db)

    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {
        "id": user.id,
        "yahoo_guid": user.yahoo_guid,
        "display_name": user.display_name,
        "email": user.email,
        "has_valid_token": user.oauth_token is not None and not user.oauth_token.is_expired,
    }


@router.get("/status")
async def auth_status(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Check authentication status.

    Returns whether user is logged in without requiring authentication.
    """
    user = get_current_user(request, db)

    if not user:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "user_id": user.id,
        "has_valid_token": user.oauth_token is not None and not user.oauth_token.is_expired,
    }
