"""
Application configuration loaded from environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    """Application settings from environment variables."""

    # Yahoo OAuth
    YAHOO_CLIENT_ID: str = os.getenv("YAHOO_CLIENT_ID", "")
    YAHOO_CLIENT_SECRET: str = os.getenv("YAHOO_CLIENT_SECRET", "")
    YAHOO_REDIRECT_URI: str = os.getenv(
        "YAHOO_REDIRECT_URI", "http://localhost:8000/auth/yahoo/callback"
    )

    # Yahoo API endpoints
    YAHOO_AUTH_URL: str = "https://api.login.yahoo.com/oauth2/request_auth"
    YAHOO_TOKEN_URL: str = "https://api.login.yahoo.com/oauth2/get_token"
    YAHOO_API_BASE: str = "https://fantasysports.yahooapis.com/fantasy/v2"

    # Application
    APP_SECRET_KEY: str = os.getenv("APP_SECRET_KEY", "dev-secret-change-in-production")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Frontend URL (where to redirect after OAuth)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:8501")

    # Database
    # Railway provides postgres:// but SQLAlchemy requires postgresql://
    _raw_db_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/data/fantasy.db")
    DATABASE_URL: str = _raw_db_url.replace("postgres://", "postgresql://", 1) if _raw_db_url.startswith("postgres://") else _raw_db_url

    # Scheduler
    SCHEDULER_DAILY_HOUR: int = int(os.getenv("SCHEDULER_DAILY_HOUR", "4"))
    SCHEDULER_DAILY_MINUTE: int = int(os.getenv("SCHEDULER_DAILY_MINUTE", "0"))

    # Cache refresh settings (lazy refresh at 6 AM Eastern daily)
    CACHE_REFRESH_HOUR: int = int(os.getenv("CACHE_REFRESH_HOUR", "6"))
    CACHE_REFRESH_TIMEZONE: str = os.getenv("CACHE_REFRESH_TIMEZONE", "America/New_York")

    # Session settings
    SESSION_EXPIRE_DAYS: int = int(os.getenv("SESSION_EXPIRE_DAYS", "30"))

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required settings are present. Returns list of missing settings."""
        missing = []
        if not cls.YAHOO_CLIENT_ID:
            missing.append("YAHOO_CLIENT_ID")
        if not cls.YAHOO_CLIENT_SECRET:
            missing.append("YAHOO_CLIENT_SECRET")
        return missing


settings = Settings()
