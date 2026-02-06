"""
Tests for OAuth/Auth flow routes.

Covers JWT tokens, auth codes, sessions, get_current_user,
/exchange, /session/validate, /session/invalidate, and device linking.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.database.models import User, OAuthToken, AuthCode, UserSession, DeviceLinkCode
from backend.routes.auth import (
    create_access_token,
    verify_token,
    create_auth_code,
    consume_auth_code,
    create_user_session,
    validate_session,
    invalidate_session,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
)


# -- JWT token tests --


class TestJWTTokens:
    """Tests for create_access_token() and verify_token()."""

    def test_create_and_verify_roundtrip(self):
        token = create_access_token(user_id=42)
        result = verify_token(token)
        assert result == 42

    def test_verify_returns_none_for_invalid_token(self):
        result = verify_token("invalid.jwt.token")
        assert result is None

    def test_verify_returns_none_for_tampered_token(self):
        token = create_access_token(user_id=42)
        tampered = token[:-5] + "XXXXX"
        result = verify_token(tampered)
        assert result is None

    def test_verify_returns_none_for_expired_token(self):
        from jose import jwt as jose_jwt

        expired_payload = {
            "sub": "1",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "type": "access",
        }
        token = jose_jwt.encode(expired_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        result = verify_token(token)
        assert result is None

    def test_verify_returns_none_for_missing_sub(self):
        from jose import jwt as jose_jwt

        payload = {
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "access",
        }
        token = jose_jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        result = verify_token(token)
        assert result is None

    def test_token_contains_correct_user_id(self):
        token = create_access_token(user_id=99)
        user_id = verify_token(token)
        assert user_id == 99


# -- Auth code tests --


class TestAuthCodes:
    """Tests for auth code creation and consumption."""

    def test_create_auth_code(self, db_session, test_user):
        code = create_auth_code(db_session, test_user.id)
        assert len(code) > 0

        record = db_session.query(AuthCode).filter(AuthCode.code == code).first()
        assert record is not None
        assert record.user_id == test_user.id
        assert record.used is False

    def test_consume_valid_code(self, db_session, test_user):
        code = create_auth_code(db_session, test_user.id)
        user_id = consume_auth_code(db_session, code)
        assert user_id == test_user.id

    def test_consume_marks_code_as_used(self, db_session, test_user):
        code = create_auth_code(db_session, test_user.id)
        consume_auth_code(db_session, code)

        # Second consumption should fail
        user_id = consume_auth_code(db_session, code)
        assert user_id is None

    def test_consume_expired_code_returns_none(self, db_session, test_user):
        code = create_auth_code(db_session, test_user.id)

        record = db_session.query(AuthCode).filter(AuthCode.code == code).first()
        record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db_session.commit()

        user_id = consume_auth_code(db_session, code)
        assert user_id is None

    def test_consume_nonexistent_code_returns_none(self, db_session):
        user_id = consume_auth_code(db_session, "nonexistent-code")
        assert user_id is None


# -- Session management tests --


class TestSessionManagement:
    """Tests for session create, validate, invalidate using real DB."""

    def test_create_session(self, db_session, test_user):
        session_id = create_user_session(db_session, test_user.id)
        assert len(session_id) > 0

        record = db_session.query(UserSession).filter(
            UserSession.session_id == session_id
        ).first()
        assert record is not None
        assert record.user_id == test_user.id

    def test_validate_valid_session(self, db_session, test_user):
        session_id = create_user_session(db_session, test_user.id)
        session = validate_session(db_session, session_id)
        assert session is not None
        assert session.user_id == test_user.id

    def test_validate_expired_session(self, db_session, test_user):
        session_id = create_user_session(db_session, test_user.id)

        record = db_session.query(UserSession).filter(
            UserSession.session_id == session_id
        ).first()
        record.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.commit()

        result = validate_session(db_session, session_id)
        assert result is None

    def test_validate_nonexistent_session(self, db_session):
        result = validate_session(db_session, "nonexistent-session-id")
        assert result is None

    def test_validate_updates_last_activity(self, db_session, test_user):
        session_id = create_user_session(db_session, test_user.id)

        record = db_session.query(UserSession).filter(
            UserSession.session_id == session_id
        ).first()
        old_activity = record.last_activity

        validate_session(db_session, session_id)

        db_session.refresh(record)
        assert record.last_activity >= old_activity

    def test_invalidate_session(self, db_session, test_user):
        session_id = create_user_session(db_session, test_user.id)
        result = invalidate_session(db_session, session_id)
        assert result is True

        record = db_session.query(UserSession).filter(
            UserSession.session_id == session_id
        ).first()
        assert record is None

    def test_invalidate_nonexistent_session(self, db_session):
        result = invalidate_session(db_session, "no-such-session")
        assert result is False


# -- Exchange flow tests (function-level, no HTTP) --


class TestExchangeFlow:
    """Tests for the auth code -> JWT exchange flow."""

    def test_exchange_valid_code_produces_jwt(self, db_session, test_user):
        """Creating and consuming a code should yield a valid JWT."""
        code = create_auth_code(db_session, test_user.id)
        user_id = consume_auth_code(db_session, code)
        assert user_id == test_user.id

        # The exchange endpoint would then call create_access_token
        jwt_token = create_access_token(user_id)
        assert verify_token(jwt_token) == test_user.id

    def test_exchange_expired_code_returns_none(self, db_session, test_user):
        code = create_auth_code(db_session, test_user.id)

        record = db_session.query(AuthCode).filter(AuthCode.code == code).first()
        record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db_session.commit()

        user_id = consume_auth_code(db_session, code)
        assert user_id is None

    def test_exchange_used_code_returns_none(self, db_session, test_user):
        code = create_auth_code(db_session, test_user.id)

        # First use
        consume_auth_code(db_session, code)

        # Second use
        user_id = consume_auth_code(db_session, code)
        assert user_id is None

    def test_exchange_invalid_code_returns_none(self, db_session):
        user_id = consume_auth_code(db_session, "totally-bogus")
        assert user_id is None


# -- Session validate/invalidate flow tests --


class TestSessionFlows:
    """Tests for session validation and invalidation flows."""

    def test_validate_produces_user_info(self, db_session, test_user):
        """Validating a session should return the user's session and allow JWT creation."""
        session_id = create_user_session(db_session, test_user.id)

        session = validate_session(db_session, session_id)
        assert session is not None

        # Load the user as the endpoint would
        user = db_session.query(User).filter(User.id == session.user_id).first()
        assert user is not None
        assert user.id == test_user.id

        jwt_token = create_access_token(user.id)
        assert verify_token(jwt_token) == test_user.id

    def test_validate_expired_session_returns_none(self, db_session, test_user):
        session_id = create_user_session(db_session, test_user.id)

        record = db_session.query(UserSession).filter(
            UserSession.session_id == session_id
        ).first()
        record.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.commit()

        result = validate_session(db_session, session_id)
        assert result is None

    def test_invalidate_removes_session(self, db_session, test_user):
        session_id = create_user_session(db_session, test_user.id)
        result = invalidate_session(db_session, session_id)
        assert result is True

        # Session should be gone
        assert validate_session(db_session, session_id) is None


# -- Device linking tests --


class TestDeviceLinking:
    """Tests for device link code generation and consumption."""

    def test_valid_device_code(self, db_session, test_user):
        code = "test-device-link-code"
        device_code = DeviceLinkCode(
            code=code,
            user_id=test_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=3),
        )
        db_session.add(device_code)
        db_session.commit()

        # Simulate the link endpoint logic
        found = db_session.query(DeviceLinkCode).filter(
            DeviceLinkCode.code == code,
            DeviceLinkCode.used == False,  # noqa: E712
        ).first()
        assert found is not None
        assert found.user_id == test_user.id
        assert not found.is_expired

    def test_expired_device_code(self, db_session, test_user):
        code = "expired-device-code"
        device_code = DeviceLinkCode(
            code=code,
            user_id=test_user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(device_code)
        db_session.commit()

        found = db_session.query(DeviceLinkCode).filter(
            DeviceLinkCode.code == code,
            DeviceLinkCode.used == False,  # noqa: E712
        ).first()
        assert found is not None
        assert found.is_expired

    def test_used_device_code(self, db_session, test_user):
        code = "used-device-code"
        device_code = DeviceLinkCode(
            code=code,
            user_id=test_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=3),
        )
        db_session.add(device_code)
        db_session.commit()

        # Mark as used
        found = db_session.query(DeviceLinkCode).filter(DeviceLinkCode.code == code).first()
        found.used = True  # type: ignore[assignment]
        db_session.commit()

        # Should not find it (used == False filter)
        found2 = db_session.query(DeviceLinkCode).filter(
            DeviceLinkCode.code == code,
            DeviceLinkCode.used == False,  # noqa: E712
        ).first()
        assert found2 is None

    def test_nonexistent_device_code(self, db_session):
        found = db_session.query(DeviceLinkCode).filter(
            DeviceLinkCode.code == "no-such-code",
            DeviceLinkCode.used == False,  # noqa: E712
        ).first()
        assert found is None


# -- get_current_user endpoint tests --


class TestGetCurrentUser:
    """Tests for the get_current_user dependency via HTTP."""

    def test_bearer_token_auth(self, client, test_user):
        token = create_access_token(test_user.id)
        response = client.get(
            "/auth/yahoo/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["id"] == test_user.id

    def test_no_auth_returns_401(self, client):
        response = client.get("/auth/yahoo/me")
        assert response.status_code == 401

    def test_invalid_bearer_token(self, client):
        response = client.get(
            "/auth/yahoo/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401
