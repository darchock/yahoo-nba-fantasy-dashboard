"""
Yahoo API Service - Instance-based handler for per-user Yahoo Fantasy API interactions.
Adapted from Yahoo_NBA_Fantasy_Hub/yahoo_api_handler.py
"""

import base64
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import User, OAuthToken
from app.logging_config import get_logger

logger = get_logger(__name__)


class YahooAPIService:
    """
    Instance-based Yahoo API handler for per-user operations.
    Each instance is associated with a specific user's OAuth tokens.
    """

    # OAuth endpoints
    OAUTH_AUTHORIZE_URL = "https://api.login.yahoo.com/oauth2/request_auth"
    OAUTH_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"

    # Yahoo Fantasy API endpoints
    FANTASY_API_BASE = "https://fantasysports.yahooapis.com/fantasy/v2"

    def __init__(self, db: Session, user: Optional[User] = None):
        """
        Initialize the Yahoo API service.

        Args:
            db: Database session
            user: User instance (optional, can be set later after OAuth)
        """
        self.db = db
        self.user = user
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    @classmethod
    def get_authorization_url(cls, state: str = "") -> str:
        """
        Generate the authorization URL for OAuth flow.

        Args:
            state: State parameter for CSRF protection (should be session-specific)

        Returns:
            Authorization URL to redirect user to
        """
        params = {
            "client_id": settings.YAHOO_CLIENT_ID,
            "redirect_uri": settings.YAHOO_REDIRECT_URI,
            "response_type": "code",
            "scope": "fspt-r",  # fantasy sports read access
            "state": state,
        }
        return f"{cls.OAUTH_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code_for_token(self, authorization_code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            authorization_code: The authorization code from OAuth callback

        Returns:
            Token data dictionary

        Raises:
            httpx.HTTPError: If token exchange fails
        """
        auth_string = base64.b64encode(
            f"{settings.YAHOO_CLIENT_ID}:{settings.YAHOO_CLIENT_SECRET}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {auth_string}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": settings.YAHOO_REDIRECT_URI,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.OAUTH_TOKEN_URL, headers=headers, data=data
            )
            response.raise_for_status()
            return response.json()

    async def refresh_access_token(self) -> Optional[Dict[str, Any]]:
        """
        Refresh the access token using the stored refresh token.

        Returns:
            New token data, or None if refresh fails
        """
        if not self.user or not self.user.oauth_token:
            logger.warning("Cannot refresh token: no user or token available")
            return None

        user_id = self.user.id
        logger.info(f"Refreshing access token for user={user_id}")

        auth_string = base64.b64encode(
            f"{settings.YAHOO_CLIENT_ID}:{settings.YAHOO_CLIENT_SECRET}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {auth_string}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.user.oauth_token.refresh_token,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.OAUTH_TOKEN_URL, headers=headers, data=data
            )
            response.raise_for_status()
            token_data = response.json()

        # Update stored token
        self._save_token(token_data)
        logger.info(f"Access token refreshed successfully for user={user_id}")
        return token_data

    def _save_token(self, token_data: Dict[str, Any]) -> None:
        """
        Save token data to database.

        Args:
            token_data: Token response from Yahoo OAuth
        """
        if not self.user:
            raise ValueError("User must be set before saving token")

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600))

        if self.user.oauth_token:
            # Update existing token
            self.user.oauth_token.access_token = token_data["access_token"]
            self.user.oauth_token.refresh_token = token_data.get(
                "refresh_token", self.user.oauth_token.refresh_token
            )
            self.user.oauth_token.expires_at = expires_at
        else:
            # Create new token
            oauth_token = OAuthToken(
                user_id=self.user.id,
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_at=expires_at,
            )
            self.db.add(oauth_token)

        self.db.commit()

        # Update cached values
        self._access_token = token_data["access_token"]
        self._token_expires_at = expires_at

    async def get_valid_access_token(self) -> Optional[str]:
        """
        Get a valid access token, refreshing if necessary.

        Returns:
            Valid access token, or None if unable to obtain one
        """
        if not self.user or not self.user.oauth_token:
            return None

        # Check if cached token is still valid (with 5 min buffer)
        if self._access_token and self._token_expires_at:
            if datetime.now(timezone.utc) < self._token_expires_at - timedelta(minutes=5):
                return self._access_token

        # Check database token
        token = self.user.oauth_token
        if not token.is_expired:
            self._access_token = token.access_token
            # Ensure expires_at is timezone-aware (SQLite stores naive datetimes)
            expires_at = token.expires_at
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            self._token_expires_at = expires_at
            return self._access_token

        # Try to refresh
        try:
            new_token = await self.refresh_access_token()
            if new_token:
                return new_token["access_token"]
        except Exception as e:
            user_id = self.user.id if self.user else "unknown"
            logger.error(f"Token refresh failed for user={user_id}: {e}")

        return None

    async def make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the Yahoo Fantasy API.

        Args:
            endpoint: The API endpoint (relative to base URL)
            method: HTTP method
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If unable to get valid token or request fails
        """
        access_token = await self.get_valid_access_token()
        if not access_token:
            logger.error("Unable to obtain valid access token for Yahoo API request")
            raise Exception("Unable to obtain valid access token")

        headers = {"Authorization": f"Bearer {access_token}"}

        # Default to JSON format
        if params is None:
            params = {}
        params["format"] = "json"

        url = f"{self.FANTASY_API_BASE}{endpoint}"

        # Log request (exclude format param from log as it's always json)
        log_params = {k: v for k, v in params.items() if k != "format"}
        user_id = self.user.id if self.user else "unknown"
        logger.info(f"Yahoo API request: {method} {endpoint} params={log_params or None} user={user_id}")

        start_time = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method, url, headers=headers, params=params
                )
                response.raise_for_status()
                elapsed_ms = (time.time() - start_time) * 1000
                logger.info(f"Yahoo API response: {endpoint} status={response.status_code} time={elapsed_ms:.0f}ms")
                return response.json()
        except httpx.HTTPStatusError as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"Yahoo API error: {endpoint} status={e.response.status_code} time={elapsed_ms:.0f}ms")
            raise

    # Convenience methods for common API calls

    async def get_user_info(self) -> Dict[str, Any]:
        """Get current user's Yahoo profile info."""
        return await self.make_request("/users;use_login=1")

    async def get_user_leagues(self, sport: str = "nba") -> List[Dict[str, Any]]:
        """
        Get all leagues for the current user.

        Args:
            sport: Sport type (nba, nfl, mlb, nhl)

        Returns:
            List of league data dictionaries
        """
        from app.parsing.helpers import safe_get

        response = await self.make_request(f"/users;use_login=1/games;game_keys={sport}/leagues")

        # Parse Yahoo's nested response structure to extract leagues
        leagues = []
        games = safe_get(response, "fantasy_content", "users", 0, "user", 1, "games", default={})

        # Games is a dict with numeric string keys ("0", "1", ...) plus "count"
        for key, game_data in games.items():
            if key == "count" or not isinstance(game_data, dict):
                continue

            game_leagues = safe_get(game_data, "game", 1, "leagues", default={})
            for league_key, league_data in game_leagues.items():
                if league_key == "count" or not isinstance(league_data, dict):
                    continue

                league_info = safe_get(league_data, "league", 0, default={})
                if league_info:
                    leagues.append(league_info)

        return leagues

    async def get_league_info(self, league_key: str) -> Dict[str, Any]:
        """Get league metadata."""
        return await self.make_request(f"/league/{league_key}")

    async def get_league_teams(self, league_key: str) -> Dict[str, Any]:
        """Get all teams in a league."""
        return await self.make_request(f"/league/{league_key}/teams")

    async def get_league_standings(
        self, league_key: str, week: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get league standings with team stats.

        Args:
            league_key: The league key
            week: Week number (None for season totals)
        """
        # Include teams/stats subresource to get individual stat categories
        endpoint = f"/league/{league_key}/standings"
        if week is not None:
            endpoint += f";week={week}"
        return await self.make_request(endpoint)

    async def get_league_scoreboard(
        self, league_key: str, week: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get league scoreboard for a specific week.

        Args:
            league_key: The league key
            week: Week number (None for current week)
        """
        endpoint = f"/league/{league_key}/scoreboard"
        params = {}
        if week is not None:
            params["week"] = week
        return await self.make_request(endpoint, params=params if params else None)

    async def get_league_transactions(
        self, league_key: str, transaction_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get league transactions.

        Args:
            league_key: The league key
            transaction_type: Filter by type (add, drop, trade, etc.)
        """
        endpoint = f"/league/{league_key}/transactions"
        params = {}
        if transaction_type:
            params["type"] = transaction_type
        return await self.make_request(endpoint, params=params if params else None)

    async def get_matchups(
        self, league_key: str, week: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get matchups for a specific week (for Pick-a-Winner game).

        Args:
            league_key: The league key
            week: Week number (None for current week)
        """
        # Matchups come from the scoreboard endpoint
        return await self.get_league_scoreboard(league_key, week)
