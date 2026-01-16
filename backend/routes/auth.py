"""
Yahoo OAuth authentication routes.
"""

import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database.connection import get_db
from app.database.models import User, OAuthToken
from app.services.yahoo_api import YahooAPIService

router = APIRouter()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """
    Get the current logged-in user from session.

    Returns:
        User if logged in, None otherwise
    """
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

    # Set session
    request.session["user_id"] = user.id

    # Redirect to frontend (configurable per environment)
    return RedirectResponse(url=settings.FRONTEND_URL)


@router.get("/logout")
async def logout(request: Request) -> dict:
    """
    Log out the current user.

    Clears the session but keeps tokens in database for potential reuse.
    """
    request.session.clear()
    return {"status": "ok", "message": "Logged out successfully"}


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
