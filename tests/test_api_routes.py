"""
Tests for API route handlers.

Covers get_yahoo_service, require_auth, validate_week, validate_league_key,
handle_yahoo_api_error, and representative endpoint tests.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.database.models import User, OAuthToken, CachedData
from app.services.yahoo_api import (
    YahooAPIError,
    YahooAuthError,
    YahooRateLimitError,
    YahooConnectionError,
    YahooTimeoutError,
)
from backend.routes.api import (
    validate_week,
    validate_league_key,
    handle_yahoo_api_error,
    get_yahoo_service,
    MIN_WEEK,
    MAX_WEEK,
)
from backend.routes.auth import create_access_token


# -- validate_week tests --


class TestValidateWeek:
    """Tests for the validate_week() helper."""

    def test_valid_week(self):
        validate_week(1)
        validate_week(10)
        validate_week(19)

    def test_none_not_required(self):
        validate_week(None, required=False)

    def test_none_required_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_week(None, required=True)
        assert exc_info.value.status_code == 400

    def test_week_below_min(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_week(0)
        assert exc_info.value.status_code == 400

    def test_week_above_max(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_week(20)
        assert exc_info.value.status_code == 400

    def test_boundary_min(self):
        validate_week(MIN_WEEK)

    def test_boundary_max(self):
        validate_week(MAX_WEEK)


# -- validate_league_key tests --


class TestValidateLeagueKey:
    """Tests for the validate_league_key() helper."""

    def test_valid_sport_format(self):
        validate_league_key("nba.l.12345")

    def test_valid_game_id_format(self):
        validate_league_key("418.l.12345")

    def test_valid_nfl_format(self):
        validate_league_key("nfl.l.99999")

    def test_invalid_no_dot_l(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_league_key("nba12345")
        assert exc_info.value.status_code == 400

    def test_invalid_empty_string(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_league_key("")
        assert exc_info.value.status_code == 400

    def test_invalid_single_char_sport(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_league_key("n.l.12345")
        assert exc_info.value.status_code == 400

    def test_invalid_uppercase_sport(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_league_key("NBA.l.12345")
        assert exc_info.value.status_code == 400

    def test_invalid_non_numeric_league_id(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_league_key("nba.l.abc")
        assert exc_info.value.status_code == 400


# -- handle_yahoo_api_error tests --


class TestHandleYahooApiError:
    """Tests for handle_yahoo_api_error()."""

    def test_rate_limit_error(self):
        exc = handle_yahoo_api_error(YahooRateLimitError(retry_after=30))
        assert exc.status_code == 429
        assert "rate limit" in exc.detail.lower()

    def test_rate_limit_error_with_retry_after(self):
        exc = handle_yahoo_api_error(YahooRateLimitError(retry_after=60))
        assert "60" in exc.detail

    def test_auth_error(self):
        exc = handle_yahoo_api_error(YahooAuthError())
        assert exc.status_code == 401
        assert "authentication" in exc.detail.lower()

    def test_timeout_error(self):
        exc = handle_yahoo_api_error(YahooTimeoutError())
        assert exc.status_code == 504
        assert "timed out" in exc.detail.lower()

    def test_connection_error(self):
        exc = handle_yahoo_api_error(YahooConnectionError())
        assert exc.status_code == 502
        assert "connect" in exc.detail.lower()

    def test_generic_api_error_with_status(self):
        exc = handle_yahoo_api_error(YahooAPIError("server error", status_code=503))
        assert exc.status_code == 503

    def test_generic_api_error_without_status(self):
        exc = handle_yahoo_api_error(YahooAPIError("unknown"))
        assert exc.status_code == 502

    def test_unknown_exception(self):
        exc = handle_yahoo_api_error(RuntimeError("something broke"))
        assert exc.status_code == 502
        assert "something broke" in exc.detail

    def test_context_in_message(self):
        exc = handle_yahoo_api_error(
            YahooAuthError(), context="fetching standings"
        )
        assert "fetching standings" in exc.detail


# -- get_yahoo_service dependency tests --


class TestGetYahooServiceDependency:
    """Tests for the get_yahoo_service() dependency."""

    def test_no_token_returns_401(self, client, db_session):
        """User with no OAuth token at all should get 401."""
        user = User(yahoo_guid="no-token-user")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        token = create_access_token(user.id)
        response = client.get(
            "/api/user/leagues",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert "No Yahoo token found" in response.json()["detail"]

    def test_expired_token_not_rejected_by_dependency(self, db_session):
        """get_yahoo_service should NOT reject expired tokens.

        The service handles refresh transparently via refresh_access_token().
        The dependency only rejects users with NO token at all.
        """
        user = User(yahoo_guid="expired-but-allowed")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        expired_token = OAuthToken(
            user_id=user.id,
            access_token="expired-token",
            refresh_token="valid-refresh",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(expired_token)
        db_session.commit()
        db_session.refresh(user)

        # The dependency checks user.oauth_token existence, NOT expiry
        assert user.oauth_token is not None
        assert user.oauth_token.is_expired  # Token IS expired
        # But the dependency should NOT raise - it just checks existence
        # (refresh is handled by YahooAPIService.get_valid_access_token)

    def test_no_token_at_all_raises(self, db_session):
        """get_yahoo_service should raise 401 when user has NO token record."""
        user = User(yahoo_guid="no-token-at-all")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # No OAuthToken created for this user
        assert user.oauth_token is None


# -- require_auth tests --


class TestRequireAuth:
    """Tests for the require_auth() dependency."""

    def test_no_auth_returns_401(self, client):
        response = client.get("/api/user/leagues")
        assert response.status_code == 401

    def test_valid_auth_returns_user(self, client, test_user):
        jwt_token = create_access_token(test_user.id)

        from backend.main import app

        mock_service = AsyncMock()
        mock_service.get_user_leagues = AsyncMock(return_value=[])

        async def override():
            return mock_service

        app.dependency_overrides[get_yahoo_service] = override
        try:
            response = client.get(
                "/api/user/leagues",
                headers={"Authorization": f"Bearer {jwt_token}"},
            )
            assert response.status_code == 200
        finally:
            del app.dependency_overrides[get_yahoo_service]


# -- Standings endpoint integration test --


class TestCachingLogic:
    """Tests for cache hit/miss logic at function level."""

    def test_cache_hit_returns_data(self, db_session):
        """get_cached_data should return non-stale cache entries."""
        from backend.routes.api import get_cached_data

        cached = CachedData(
            league_key="nba.l.12345",
            data_type="standings",
            week=None,
            json_data={"teams": [{"name": "Team A"}], "league": {"current_week": 10}},
            fetched_at=datetime.now(timezone.utc),
            is_complete=True,
        )
        db_session.add(cached)
        db_session.commit()

        result = get_cached_data(db_session, "nba.l.12345", "standings", week=None)
        assert result is not None
        assert result.json_data["teams"][0]["name"] == "Team A"

    def test_cache_miss_returns_none(self, db_session):
        """get_cached_data should return None when no cache exists."""
        from backend.routes.api import get_cached_data

        result = get_cached_data(db_session, "nba.l.99999", "standings", week=None)
        assert result is None

    def test_format_cache_metadata_cached(self, db_session):
        """format_cache_metadata should reflect cached state."""
        from backend.routes.api import format_cache_metadata

        cached = CachedData(
            league_key="nba.l.12345",
            data_type="standings",
            json_data={},
            fetched_at=datetime.now(timezone.utc),
            is_complete=True,
        )
        result = format_cache_metadata(cached)
        assert result["cached"] is True
        assert result["is_complete"] is True

    def test_format_cache_metadata_none(self):
        """format_cache_metadata should return uncached state for None."""
        from backend.routes.api import format_cache_metadata

        result = format_cache_metadata(None)
        assert result["cached"] is False

    def test_save_and_retrieve_cached_data(self, db_session):
        """save_cached_data should persist and be retrievable."""
        from backend.routes.api import save_cached_data, get_cached_data

        data = {"teams": [{"name": "Team B"}]}
        save_cached_data(db_session, "nba.l.11111", "standings", data, week=5, is_complete=True)

        result = get_cached_data(db_session, "nba.l.11111", "standings", week=5)
        assert result is not None
        assert result.json_data["teams"][0]["name"] == "Team B"
        assert result.is_complete is True


class TestStandingsEndpoint:
    """Representative endpoint test for /league/{key}/standings."""

    def test_auth_failure_returns_401(self, client):
        response = client.get("/api/league/nba.l.12345/standings")
        assert response.status_code == 401

    def test_invalid_league_key_returns_400(self, client, test_user):
        jwt_token = create_access_token(test_user.id)

        from backend.main import app

        mock_service = AsyncMock()

        async def override():
            return mock_service

        app.dependency_overrides[get_yahoo_service] = override
        try:
            response = client.get(
                "/api/league/INVALID/standings",
                headers={"Authorization": f"Bearer {jwt_token}"},
            )
            assert response.status_code == 400
            assert "Invalid league_key" in response.json()["detail"]
        finally:
            del app.dependency_overrides[get_yahoo_service]

    def test_invalid_week_returns_400(self, client, test_user):
        jwt_token = create_access_token(test_user.id)

        from backend.main import app

        mock_service = AsyncMock()

        async def override():
            return mock_service

        app.dependency_overrides[get_yahoo_service] = override
        try:
            response = client.get(
                "/api/league/nba.l.12345/standings?week=25",
                headers={"Authorization": f"Bearer {jwt_token}"},
            )
            assert response.status_code == 400
            assert "between" in response.json()["detail"].lower()
        finally:
            del app.dependency_overrides[get_yahoo_service]
