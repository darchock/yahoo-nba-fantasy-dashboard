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
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/data/fantasy.db")

    # Scheduler
    SCHEDULER_DAILY_HOUR: int = int(os.getenv("SCHEDULER_DAILY_HOUR", "4"))
    SCHEDULER_DAILY_MINUTE: int = int(os.getenv("SCHEDULER_DAILY_MINUTE", "0"))

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
