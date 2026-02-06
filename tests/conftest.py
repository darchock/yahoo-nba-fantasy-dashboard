"""
Shared test fixtures for Yahoo Fantasy Dashboard tests.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.database.models import Base, User, OAuthToken, UserSession


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine):
    """Create a database session for testing."""
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine, expire_on_commit=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """
    Create a FastAPI TestClient with DB dependency overridden.

    All endpoint tests should use this fixture to ensure the same
    in-memory DB session is used throughout.
    """
    from fastapi.testclient import TestClient
    from backend.main import app
    from app.database.connection import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create an authenticated test user with a valid OAuth token."""
    user = User(
        yahoo_guid="test-guid-12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = OAuthToken(
        user_id=user.id,
        access_token="test-access-token",
        refresh_token="test-refresh-token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(token)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def expired_token_user(db_session: Session) -> User:
    """Create a test user with an expired OAuth token."""
    user = User(
        yahoo_guid="expired-guid-99999",
        email="expired@example.com",
        display_name="Expired User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = OAuthToken(
        user_id=user.id,
        access_token="expired-access-token",
        refresh_token="valid-refresh-token",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add(token)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def mock_yahoo_service():
    """Create a mock YahooAPIService."""
    service = MagicMock()
    service.get_league_standings = AsyncMock(return_value={"fantasy_content": {}})
    service.get_league_scoreboard = AsyncMock(return_value={"fantasy_content": {}})
    service.get_league_teams = AsyncMock(return_value={"fantasy_content": {}})
    service.get_league_info = AsyncMock(return_value={"fantasy_content": {}})
    service.get_user_leagues = AsyncMock(return_value=[])
    service.get_league_transactions = AsyncMock(return_value={"fantasy_content": {}})
    service.make_request = AsyncMock(return_value={"fantasy_content": {}})
    return service
