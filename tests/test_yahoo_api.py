"""
Tests for Yahoo API Service.

Covers token management, request execution, 401 retry logic,
exception hierarchy, and token persistence.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.database.models import User, OAuthToken
from app.services.yahoo_api import (
    YahooAPIService,
    YahooAPIError,
    YahooAuthError,
    YahooRateLimitError,
    YahooConnectionError,
    YahooTimeoutError,
)


# -- Exception hierarchy tests --


class TestExceptionHierarchy:
    """Test custom exception classes."""

    def test_yahoo_api_error_base(self):
        e = YahooAPIError("test error", status_code=500)
        assert e.message == "test error"
        assert e.status_code == 500
        assert str(e) == "test error"

    def test_yahoo_api_error_no_status(self):
        e = YahooAPIError("msg")
        assert e.status_code is None

    def test_yahoo_rate_limit_error(self):
        e = YahooRateLimitError(retry_after=60)
        assert e.retry_after == 60
        assert e.status_code == 429
        assert "60s" in e.message

    def test_yahoo_rate_limit_error_no_retry_after(self):
        e = YahooRateLimitError()
        assert e.retry_after is None
        assert e.status_code == 429

    def test_yahoo_auth_error(self):
        e = YahooAuthError()
        assert e.status_code == 401

    def test_yahoo_auth_error_custom_message(self):
        e = YahooAuthError("custom msg")
        assert e.message == "custom msg"
        assert e.status_code == 401

    def test_yahoo_connection_error(self):
        e = YahooConnectionError()
        assert e.status_code is None
        assert "connect" in e.message.lower()

    def test_yahoo_timeout_error(self):
        e = YahooTimeoutError()
        assert e.status_code is None
        assert "timed out" in e.message.lower()

    def test_all_inherit_from_base(self):
        assert issubclass(YahooRateLimitError, YahooAPIError)
        assert issubclass(YahooAuthError, YahooAPIError)
        assert issubclass(YahooConnectionError, YahooAPIError)
        assert issubclass(YahooTimeoutError, YahooAPIError)


# -- get_valid_access_token tests --


class TestGetValidAccessToken:
    """Tests for YahooAPIService.get_valid_access_token()."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_user(self):
        service = YahooAPIService(db=MagicMock(), user=None)
        result = await service.get_valid_access_token()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_token(self):
        user = MagicMock(spec=User)
        user.oauth_token = None
        service = YahooAPIService(db=MagicMock(), user=user)
        result = await service.get_valid_access_token()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_token_when_valid(self, test_user, db_session):
        service = YahooAPIService(db=db_session, user=test_user)
        result = await service.get_valid_access_token()
        assert result == "test-access-token"

    @pytest.mark.asyncio
    async def test_refreshes_when_expired(self, expired_token_user, db_session):
        service = YahooAPIService(db=db_session, user=expired_token_user)

        new_token_data = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
        }
        service.refresh_access_token = AsyncMock(return_value=new_token_data)

        result = await service.get_valid_access_token()
        assert result == "new-access-token"
        service.refresh_access_token.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_refresh_fails(self, expired_token_user, db_session):
        service = YahooAPIService(db=db_session, user=expired_token_user)
        service.refresh_access_token = AsyncMock(return_value=None)

        result = await service.get_valid_access_token()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_refresh_raises(self, expired_token_user, db_session):
        service = YahooAPIService(db=db_session, user=expired_token_user)
        service.refresh_access_token = AsyncMock(side_effect=Exception("network error"))

        result = await service.get_valid_access_token()
        assert result is None


# -- _save_token tests --


class TestSaveToken:
    """Tests for YahooAPIService._save_token()."""

    def test_save_token_updates_existing(self, test_user, db_session):
        service = YahooAPIService(db=db_session, user=test_user)

        token_data = {
            "access_token": "updated-token",
            "refresh_token": "updated-refresh",
            "expires_in": 7200,
        }
        service._save_token(token_data)

        # Verify in DB
        db_session.refresh(test_user)
        assert test_user.oauth_token.access_token == "updated-token"
        assert test_user.oauth_token.refresh_token == "updated-refresh"

    def test_save_token_creates_new(self, db_session):
        user = User(yahoo_guid="no-token-user")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        service = YahooAPIService(db=db_session, user=user)
        token_data = {
            "access_token": "brand-new-token",
            "refresh_token": "brand-new-refresh",
            "expires_in": 3600,
        }
        service._save_token(token_data)

        db_session.refresh(user)
        assert user.oauth_token is not None
        assert user.oauth_token.access_token == "brand-new-token"

    def test_save_token_preserves_refresh_token_if_not_in_response(self, test_user, db_session):
        service = YahooAPIService(db=db_session, user=test_user)

        token_data = {
            "access_token": "new-access",
            "expires_in": 3600,
            # No refresh_token in response
        }
        service._save_token(token_data)

        db_session.refresh(test_user)
        assert test_user.oauth_token.access_token == "new-access"
        assert test_user.oauth_token.refresh_token == "test-refresh-token"  # Original preserved

    def test_save_token_raises_without_user(self, db_session):
        service = YahooAPIService(db=db_session, user=None)
        with pytest.raises(ValueError, match="User must be set"):
            service._save_token({"access_token": "x", "refresh_token": "y"})


# -- make_request tests --


class TestMakeRequest:
    """Tests for YahooAPIService.make_request()."""

    @pytest.mark.asyncio
    async def test_raises_auth_error_when_no_token(self):
        user = MagicMock(spec=User)
        user.oauth_token = None
        user.id = 1
        service = YahooAPIService(db=MagicMock(), user=user)

        with pytest.raises(YahooAuthError, match="Unable to obtain valid access token"):
            await service.make_request("/test/endpoint")

    @pytest.mark.asyncio
    async def test_builds_correct_headers_and_params(self, test_user, db_session):
        service = YahooAPIService(db=db_session, user=test_user)

        # Mock _execute_request_with_retry to capture args
        expected_response = {"fantasy_content": {"test": True}}
        service._execute_request_with_retry = AsyncMock(return_value=expected_response)

        result = await service.make_request("/league/nba.l.123/standings", params={"week": 5})

        assert result == expected_response
        call_args = service._execute_request_with_retry.call_args
        method, url, headers, params = call_args[0][:4]

        assert method == "GET"
        assert url.endswith("/league/nba.l.123/standings")
        assert headers["Authorization"] == "Bearer test-access-token"
        assert params["format"] == "json"
        assert params["week"] == 5

    @pytest.mark.asyncio
    async def test_adds_format_json_when_no_params(self, test_user, db_session):
        service = YahooAPIService(db=db_session, user=test_user)
        service._execute_request_with_retry = AsyncMock(return_value={})

        await service.make_request("/test")

        call_args = service._execute_request_with_retry.call_args
        params = call_args[0][3]
        assert params["format"] == "json"


# -- 401 retry logic tests --


class TestMakeRequest401Retry:
    """Tests for the 401-retry-with-refresh logic in make_request()."""

    @pytest.mark.asyncio
    async def test_retries_after_401_with_refreshed_token(self, test_user, db_session):
        service = YahooAPIService(db=db_session, user=test_user)

        # First call raises 401, second succeeds
        expected_response = {"data": "success"}
        service._execute_request_with_retry = AsyncMock(
            side_effect=[YahooAuthError("401"), expected_response]
        )
        service.refresh_access_token = AsyncMock(
            return_value={"access_token": "refreshed-token", "expires_in": 3600}
        )

        result = await service.make_request("/test")

        assert result == expected_response
        assert service._execute_request_with_retry.await_count == 2
        service.refresh_access_token.assert_awaited_once()

        # Verify second call used refreshed token
        second_call_headers = service._execute_request_with_retry.call_args_list[1][0][2]
        assert second_call_headers["Authorization"] == "Bearer refreshed-token"

    @pytest.mark.asyncio
    async def test_raises_auth_error_when_refresh_returns_none(self, test_user, db_session):
        service = YahooAPIService(db=db_session, user=test_user)

        service._execute_request_with_retry = AsyncMock(
            side_effect=YahooAuthError("401")
        )
        service.refresh_access_token = AsyncMock(return_value=None)

        with pytest.raises(YahooAuthError, match="Token refresh failed"):
            await service.make_request("/test")

    @pytest.mark.asyncio
    async def test_raises_auth_error_when_refresh_raises_exception(self, test_user, db_session):
        service = YahooAPIService(db=db_session, user=test_user)

        service._execute_request_with_retry = AsyncMock(
            side_effect=YahooAuthError("401")
        )
        service.refresh_access_token = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "refresh failed", request=MagicMock(), response=MagicMock()
            )
        )

        with pytest.raises(YahooAuthError, match="Token refresh failed"):
            await service.make_request("/test")

    @pytest.mark.asyncio
    async def test_does_not_retry_on_rate_limit(self, test_user, db_session):
        """Rate limit errors should NOT trigger the 401 retry path."""
        service = YahooAPIService(db=db_session, user=test_user)

        service._execute_request_with_retry = AsyncMock(
            side_effect=YahooRateLimitError(retry_after=30)
        )

        with pytest.raises(YahooRateLimitError):
            await service.make_request("/test")

        # Should NOT have attempted refresh
        assert service._execute_request_with_retry.await_count == 1

    @pytest.mark.asyncio
    async def test_second_401_after_refresh_still_raises(self, test_user, db_session):
        """If retry after refresh also gets 401, should raise (not loop)."""
        service = YahooAPIService(db=db_session, user=test_user)

        service._execute_request_with_retry = AsyncMock(
            side_effect=YahooAuthError("401")
        )
        service.refresh_access_token = AsyncMock(
            return_value={"access_token": "refreshed-token", "expires_in": 3600}
        )

        with pytest.raises(YahooAuthError):
            await service.make_request("/test")

        # Should have called execute twice (original + retry), then propagated
        assert service._execute_request_with_retry.await_count == 2


# -- refresh_access_token tests --


class TestRefreshAccessToken:
    """Tests for YahooAPIService.refresh_access_token()."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_user(self):
        service = YahooAPIService(db=MagicMock(), user=None)
        result = await service.refresh_access_token()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_token(self):
        user = MagicMock(spec=User)
        user.oauth_token = None
        service = YahooAPIService(db=MagicMock(), user=user)
        result = await service.refresh_access_token()
        assert result is None

    @pytest.mark.asyncio
    async def test_sends_correct_credentials(self, test_user, db_session):
        service = YahooAPIService(db=db_session, user=test_user)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-token",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.yahoo_api.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await service.refresh_access_token()

        assert result["access_token"] == "new-token"

        # Verify the POST was made with correct data
        post_call = mock_client.post.call_args
        assert post_call[0][0] == YahooAPIService.OAUTH_TOKEN_URL
        assert post_call[1]["data"]["grant_type"] == "refresh_token"
        assert post_call[1]["data"]["refresh_token"] == "test-refresh-token"

    @pytest.mark.asyncio
    async def test_updates_db_token(self, test_user, db_session):
        service = YahooAPIService(db=db_session, user=test_user)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "refreshed-access",
            "refresh_token": "refreshed-refresh",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.yahoo_api.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await service.refresh_access_token()

        db_session.refresh(test_user)
        assert test_user.oauth_token.access_token == "refreshed-access"
        assert test_user.oauth_token.refresh_token == "refreshed-refresh"


# -- _execute_request_with_retry tests --


class TestExecuteRequestWithRetry:
    """Tests for _execute_request_with_retry()."""

    @pytest.mark.asyncio
    async def test_handles_429_rate_limit(self, test_user, db_session):
        service = YahooAPIService(db=db_session, user=test_user)

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "120"}

        with patch("app.services.yahoo_api.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(YahooRateLimitError) as exc_info:
                await service._execute_request_with_retry(
                    "GET", "https://example.com", {}, {}, "/test", 1
                )

            assert exc_info.value.retry_after == 120

    @pytest.mark.asyncio
    async def test_handles_401_auth_error(self, test_user, db_session):
        service = YahooAPIService(db=db_session, user=test_user)

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("app.services.yahoo_api.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(YahooAuthError):
                await service._execute_request_with_retry(
                    "GET", "https://example.com", {}, {}, "/test", 1
                )

    @pytest.mark.asyncio
    async def test_handles_json_parse_error(self, test_user, db_session):
        service = YahooAPIService(db=db_session, user=test_user)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = ValueError("bad json")

        with patch("app.services.yahoo_api.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(YahooAPIError, match="Failed to parse"):
                await service._execute_request_with_retry(
                    "GET", "https://example.com", {}, {}, "/test", 1
                )

    @pytest.mark.asyncio
    async def test_handles_successful_response(self, test_user, db_session):
        service = YahooAPIService(db=db_session, user=test_user)

        expected = {"fantasy_content": {"league": {}}}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = expected

        with patch("app.services.yahoo_api.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await service._execute_request_with_retry(
                "GET", "https://example.com", {}, {}, "/test", 1
            )
            assert result == expected
