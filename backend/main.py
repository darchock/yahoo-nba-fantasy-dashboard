"""
FastAPI backend application entry point.

Run with:
    python -m uvicorn backend.main:app --host localhost --port 8080 --ssl-keyfile key.pem --ssl-certfile cert.pem --reload
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database.connection import engine
from app.database.models import Base
from app.logging_config import get_logger, silence_noisy_loggers
from backend.routes import auth, api
from backend.routes.auth import callback as oauth_callback

logger = get_logger(__name__)

# Log immediately when module is imported (helps debug startup issues)
logger.info("Backend module loaded - initializing FastAPI application")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler - runs on startup and shutdown."""
    # Silence noisy loggers (after uvicorn has configured them)
    silence_noisy_loggers()

    # Startup: Create database tables
    logger.info("Starting Yahoo Fantasy Dashboard API")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")
    yield
    # Shutdown: cleanup if needed
    logger.info("Shutting down Yahoo Fantasy Dashboard API")


app = FastAPI(
    title="Yahoo Fantasy Dashboard API",
    description="Backend API for Yahoo Fantasy Basketball Dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware - allow Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",  # Streamlit default
        "http://127.0.0.1:8501",
        "https://*.streamlit.app",  # Streamlit Cloud
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware for OAuth state
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.APP_SECRET_KEY,
    max_age=3600,  # 1 hour session
    same_site="lax",
    https_only=not settings.DEBUG,  # Require HTTPS in production only
)

# Include routers
app.include_router(auth.router, prefix="/auth/yahoo", tags=["auth"])
app.include_router(api.router, prefix="/api", tags=["api"])

# OAuth callback at root level (to match Yahoo's redirect URI)
app.get("/callback", tags=["auth"])(oauth_callback)


@app.get("/")
async def root() -> dict:
    """Root endpoint - health check."""
    return {"status": "ok", "message": "Yahoo Fantasy Dashboard API"}


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler to prevent stack traces from leaking to users.

    Logs the full exception with traceback for debugging, but returns
    a generic error message to the client.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
