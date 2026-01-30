"""
FastAPI backend application entry point.

Run with:
    python -m uvicorn backend.main:app --host localhost --port 8080 --ssl-keyfile key.pem --ssl-certfile cert.pem --reload
"""

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database.connection import engine
from app.database.models import Base
from app.logging_config import get_logger, silence_noisy_loggers
from backend.correlation import correlation_id_var, get_correlation_id
from backend.routes import auth, api
from backend.routes.auth import callback as oauth_callback

logger = get_logger(__name__)

# Log immediately when module is imported (helps debug startup issues)
logger.info("Backend module loaded - initializing FastAPI application")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds a correlation ID to each request.

    The correlation ID is:
    - Generated as a new UUID if not provided in the X-Correlation-ID header
    - Stored in a context variable accessible throughout the request lifecycle
    - Added to the response headers for client-side tracing
    """

    async def dispatch(self, request: Request, call_next):
        # Get existing correlation ID from header or generate a new one
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())[:8]  # Short ID for readability

        # Store in context variable for access in logging
        token = correlation_id_var.set(correlation_id)

        # Store on request state for access in route handlers
        request.state.correlation_id = correlation_id

        try:
            response = await call_next(request)
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            # Reset context variable
            correlation_id_var.reset(token)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler - runs on startup and shutdown."""
    from sqlalchemy import inspect, text

    # Silence noisy loggers (after uvicorn has configured them)
    silence_noisy_loggers()

    # Startup: Create database tables
    print(f"[STARTUP] Starting Yahoo Fantasy Dashboard API", flush=True)
    print(f"[STARTUP] DATABASE_URL: {settings.DATABASE_URL[:50]}...", flush=True)
    logger.info("Starting Yahoo Fantasy Dashboard API")

    # Test database connection first
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(f"[STARTUP] Database connection test: OK", flush=True)
    except Exception as e:
        print(f"[STARTUP] Database connection FAILED: {e}", flush=True)
        raise

    try:
        Base.metadata.create_all(bind=engine)
        print(f"[STARTUP] create_all() completed", flush=True)

        # Verify tables were created
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"[STARTUP] Tables in database: {tables}", flush=True)
        logger.info(f"Database tables initialized: {tables}")
    except Exception as e:
        print(f"[STARTUP] ERROR creating tables: {e}", flush=True)
        logger.error(f"Failed to create database tables: {e}")
        raise
    yield
    # Shutdown: cleanup if needed
    logger.info("Shutting down Yahoo Fantasy Dashboard API")


app = FastAPI(
    title="Yahoo Fantasy Dashboard API",
    description="Backend API for Yahoo Fantasy Basketball Dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

# Correlation ID middleware - must be added first (outermost)
app.add_middleware(CorrelationIdMiddleware)

# CORS middleware - allow Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",  # Streamlit default
        "http://127.0.0.1:8501",
        "https://*.streamlit.app",  # Streamlit Cloud
        "https://*.up.railway.app",  # Railway
        # Production: Add your domain here, e.g., "https://your-domain.com"
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
    cid = get_correlation_id() or "unknown"
    logger.error(f"[{cid}] Unhandled exception: {exc}", exc_info=True)

    response = JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "correlation_id": cid},
    )
    response.headers["X-Correlation-ID"] = cid
    return response
