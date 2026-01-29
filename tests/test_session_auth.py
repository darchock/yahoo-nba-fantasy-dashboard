"""
Tests for session-based authentication.

Tests the UserSession model and session management functions.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.database.models import User, UserSession


class TestUserSessionModel:
    """Tests for the UserSession model."""

    def test_is_expired_when_expired(self):
        """Session should be expired when expires_at is in the past."""
        session = UserSession(
            session_id="test_session",
            user_id=1,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert session.is_expired is True

    def test_is_expired_when_not_expired(self):
        """Session should not be expired when expires_at is in the future."""
        session = UserSession(
            session_id="test_session",
            user_id=1,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        assert session.is_expired is False

    def test_is_expired_handles_naive_datetime(self):
        """Session should handle naive datetimes by assuming UTC."""
        # Create a naive datetime in the past
        session = UserSession(
            session_id="test_session",
            user_id=1,
            expires_at=datetime(2020, 1, 1, 0, 0, 0),  # Naive datetime
        )
        assert session.is_expired is True

    def test_is_expired_when_expires_at_is_none(self):
        """Session should be expired when expires_at is None."""
        session = UserSession(
            session_id="test_session",
            user_id=1,
            expires_at=None,  # type: ignore[arg-type]
        )
        assert session.is_expired is True

    def test_touch_updates_last_activity(self):
        """touch() should update last_activity timestamp."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=1)
        session = UserSession(
            session_id="test_session",
            user_id=1,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            last_activity=old_time,
        )

        session.touch()

        # last_activity should be more recent than old_time
        assert session.last_activity > old_time


class TestSessionManagement:
    """Tests for session management functions in auth routes."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    def test_create_user_session_generates_unique_id(self, mock_db):
        """create_user_session should generate a unique session ID."""
        from backend.routes.auth import create_user_session

        # Mock the cleanup function to do nothing
        with patch("backend.routes.auth.cleanup_expired_sessions"):
            session_id1 = create_user_session(mock_db, user_id=1)
            session_id2 = create_user_session(mock_db, user_id=1)

        assert session_id1 != session_id2
        assert len(session_id1) == 64  # 48 bytes base64 encoded

    def test_validate_session_returns_none_for_invalid_session(self, mock_db):
        """validate_session should return None for non-existent session."""
        from backend.routes.auth import validate_session

        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = validate_session(mock_db, "invalid_session_id")

        assert result is None

    def test_validate_session_returns_none_for_expired_session(self, mock_db):
        """validate_session should return None and delete expired session."""
        from backend.routes.auth import validate_session

        expired_session = UserSession(
            session_id="expired_session",
            user_id=1,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        mock_db.query.return_value.filter.return_value.first.return_value = expired_session

        result = validate_session(mock_db, "expired_session")

        assert result is None
        mock_db.delete.assert_called_once_with(expired_session)
        mock_db.commit.assert_called()

    def test_validate_session_returns_session_and_touches_it(self, mock_db):
        """validate_session should return valid session and update last_activity."""
        from backend.routes.auth import validate_session

        old_activity = datetime.now(timezone.utc) - timedelta(hours=1)
        valid_session = UserSession(
            session_id="valid_session",
            user_id=1,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            last_activity=old_activity,
        )
        mock_db.query.return_value.filter.return_value.first.return_value = valid_session

        result = validate_session(mock_db, "valid_session")

        assert result == valid_session
        assert valid_session.last_activity > old_activity
        mock_db.commit.assert_called()

    def test_invalidate_session_returns_true_when_found(self, mock_db):
        """invalidate_session should return True when session exists."""
        from backend.routes.auth import invalidate_session

        mock_db.query.return_value.filter.return_value.delete.return_value = 1

        result = invalidate_session(mock_db, "session_to_delete")

        assert result is True

    def test_invalidate_session_returns_false_when_not_found(self, mock_db):
        """invalidate_session should return False when session doesn't exist."""
        from backend.routes.auth import invalidate_session

        mock_db.query.return_value.filter.return_value.delete.return_value = 0

        result = invalidate_session(mock_db, "nonexistent_session")

        assert result is False

    def test_invalidate_all_user_sessions_deletes_all(self, mock_db):
        """invalidate_all_user_sessions should delete all user sessions."""
        from backend.routes.auth import invalidate_all_user_sessions

        mock_db.query.return_value.filter.return_value.delete.return_value = 3

        result = invalidate_all_user_sessions(mock_db, user_id=1)

        assert result == 3


class TestSessionExpiry:
    """Tests for session expiry configuration."""

    def test_session_expires_after_configured_days(self):
        """Sessions should expire after SESSION_EXPIRE_DAYS."""
        from backend.routes.auth import create_user_session
        from app.config import settings

        mock_db = MagicMock()

        with patch("backend.routes.auth.cleanup_expired_sessions"):
            create_user_session(mock_db, user_id=1)

        # Verify the session was added with correct expiry
        add_call = mock_db.add.call_args
        added_session = add_call[0][0]

        # Expiry should be approximately SESSION_EXPIRE_DAYS from now
        expected_expiry = datetime.now(timezone.utc) + timedelta(days=settings.SESSION_EXPIRE_DAYS)
        time_diff = abs((added_session.expires_at - expected_expiry).total_seconds())
        assert time_diff < 5  # Within 5 seconds
