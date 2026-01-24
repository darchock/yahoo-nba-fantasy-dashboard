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
    predictions = relationship("MatchupPrediction", back_populates="user")


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
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("league_key", "week", "data_type", name="uq_cached_data"),
    )

    @property
    def is_stale(self) -> bool:
        """Check if cached data is expired."""
        if self.expires_at is None:
            return False
        # Handle both naive and aware datetimes from database
        expires = self.expires_at
        if expires.tzinfo is None:
            # Assume UTC if naive
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires


# Pick-a-Winner Game Models

class MatchupPrediction(Base):
    """User predictions for weekly matchups."""

    __tablename__ = "matchup_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    league_key = Column(String(50), nullable=False, index=True)
    week = Column(Integer, nullable=False)
    matchup_id = Column(String(50), nullable=False)  # Unique identifier for the matchup
    team1_key = Column(String(50), nullable=False)
    team2_key = Column(String(50), nullable=False)
    predicted_winner_key = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="predictions")
    result = relationship("PredictionResult", back_populates="prediction", uselist=False)

    __table_args__ = (
        UniqueConstraint("user_id", "league_key", "week", "matchup_id", name="uq_user_prediction"),
    )


class PredictionResult(Base):
    """Results of predictions after matchups complete."""

    __tablename__ = "prediction_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prediction_id = Column(Integer, ForeignKey("matchup_predictions.id"), unique=True, nullable=False)
    actual_winner_key = Column(String(50), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    points_earned = Column(Integer, default=0)
    calculated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    prediction = relationship("MatchupPrediction", back_populates="result")


class PredictionStandings(Base):
    """Aggregated prediction standings per user per league."""

    __tablename__ = "prediction_standings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    league_key = Column(String(50), nullable=False, index=True)
    total_correct = Column(Integer, default=0)
    total_predictions = Column(Integer, default=0)
    current_streak = Column(Integer, default=0)
    best_streak = Column(Integer, default=0)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "league_key", name="uq_prediction_standings"),
    )

    @property
    def accuracy(self) -> float:
        """Calculate prediction accuracy percentage."""
        if self.total_predictions == 0:  # type: ignore[union-attr]
            return 0.0
        return (self.total_correct / self.total_predictions) * 100  # type: ignore[return-value]


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


# Scheduler Models

class JobLog(Base):
    """Log of scheduled job executions."""

    __tablename__ = "job_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)  # started, completed, failed
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    records_processed = Column(Integer, default=0)


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
