"""
SQLAlchemy database models for Yahoo Fantasy Dashboard.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class User(Base):
    """User account - linked to Yahoo OAuth."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    yahoo_guid = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=True)
    display_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    oauth_token = relationship("OAuthToken", back_populates="user", uselist=False)
    leagues = relationship("UserLeague", back_populates="user")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")


class OAuthToken(Base):
    """Yahoo OAuth tokens for a user."""

    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    token_type = Column(String(50), default="bearer")
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="oauth_token")

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if self.expires_at is None:
            return True
        # Handle both naive and aware datetimes from database
        expires = self.expires_at
        if expires.tzinfo is None:
            # Assume UTC if naive
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires


class UserLeague(Base):
    """Leagues a user has access to."""

    __tablename__ = "user_leagues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    league_key = Column(String(50), nullable=False, index=True)
    league_id = Column(String(20), nullable=False)
    league_name = Column(String(255), nullable=True)
    sport = Column(String(20), default="nba")
    season = Column(String(10), nullable=True)
    num_teams = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # Transaction sync tracking
    last_transaction_sync_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="leagues")

    __table_args__ = (
        UniqueConstraint("user_id", "league_key", name="uq_user_league"),
    )


class CachedData(Base):
    """Cached API responses to reduce Yahoo API calls."""

    __tablename__ = "cached_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    league_key = Column(String(50), nullable=False, index=True)
    week = Column(Integer, nullable=True)
    data_type = Column(String(50), nullable=False)  # scoreboard, standings, transactions, etc.
    json_data = Column(JSON, nullable=False)
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)  # Kept for backwards compatibility, but lazy refresh is used
    is_complete = Column(Boolean, default=False)  # True for completed weeks that never need refresh

    __table_args__ = (
        UniqueConstraint("league_key", "week", "data_type", name="uq_cached_data"),
    )

    @property
    def is_stale(self) -> bool:
        """
        Check if cached data should be refreshed.

        Uses lazy refresh strategy:
        - Complete data (historical weeks): Never stale
        - Current data: Stale if fetched before today's 6 AM Eastern refresh boundary
        """
        # Complete data never goes stale
        if self.is_complete:
            return False

        # If no fetched_at, consider stale
        if self.fetched_at is None:
            return True

        # Use lazy refresh logic - import here to avoid circular imports
        from app.services.cache_utils import should_refresh_cache

        # Handle both naive and aware datetimes from database
        fetched = self.fetched_at
        if fetched.tzinfo is None:
            # Assume UTC if naive
            fetched = fetched.replace(tzinfo=timezone.utc)

        return should_refresh_cache(fetched)


# Authentication Models

class AuthCode(Base):
    """Short-lived authorization codes for OAuth redirect flow."""

    __tablename__ = "auth_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DeviceLinkCode(Base):
    """
    Short-lived codes for QR-based device linking.

    Allows users logged in on one device (e.g., desktop) to generate a QR code
    that can be scanned on another device (e.g., mobile) to login without OAuth.
    """

    __tablename__ = "device_link_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def is_expired(self) -> bool:
        """Check if code has expired."""
        if self.expires_at is None:
            return True
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires


class UserSession(Base):
    """
    Persistent user sessions for browser cookie authentication.

    Sessions allow users to stay logged in across page refreshes.
    The session_id is stored in a browser cookie and validated on each request.
    """

    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)
    last_activity = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="sessions")

    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        if self.expires_at is None:
            return True
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires

    def touch(self) -> None:
        """Update last_activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)


# Transaction Models


class Transaction(Base):
    """Individual transaction record from Yahoo Fantasy."""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String(20), nullable=False)  # Yahoo's transaction ID
    league_key = Column(String(50), nullable=False, index=True)
    type = Column(String(20), nullable=False)  # add, drop, trade, add/drop
    status = Column(String(20), nullable=False)  # successful, etc.
    timestamp = Column(Integer, nullable=False)  # Unix timestamp from Yahoo
    transaction_date = Column(DateTime, nullable=False)  # Derived from timestamp
    trader_team_key = Column(String(50), nullable=True)  # For trades
    tradee_team_key = Column(String(50), nullable=True)  # For trades
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship
    players = relationship(
        "TransactionPlayer", back_populates="transaction", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("league_key", "transaction_id", name="uq_league_transaction"),
    )


class TransactionPlayer(Base):
    """Player involved in a transaction."""

    __tablename__ = "transaction_players"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(
        Integer, ForeignKey("transactions.id"), nullable=False, index=True
    )
    player_id = Column(String(20), nullable=False, index=True)
    player_name = Column(String(100), nullable=False)
    nba_team = Column(String(10), nullable=True)
    position = Column(String(20), nullable=True)
    action_type = Column(String(10), nullable=False)  # add, drop, trade
    source_type = Column(String(20), nullable=True)  # waivers, freeagents, team
    source_team_key = Column(String(50), nullable=True, index=True)
    source_team_name = Column(String(100), nullable=True)  # Display name (supports RTL)
    destination_type = Column(String(20), nullable=True)  # waivers, team
    destination_team_key = Column(String(50), nullable=True, index=True)
    destination_team_name = Column(String(100), nullable=True)  # Display name (supports RTL)

    # Relationship
    transaction = relationship("Transaction", back_populates="players")
