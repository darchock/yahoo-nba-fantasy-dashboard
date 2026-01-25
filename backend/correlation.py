"""
Request correlation ID management.

Provides a correlation ID for request tracing throughout the application.
The correlation ID is set by middleware and can be accessed from any module.
"""

from contextvars import ContextVar
from typing import Optional

# Context variable for request correlation ID (accessible throughout the request lifecycle)
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> Optional[str]:
    """Get the current request's correlation ID."""
    return correlation_id_var.get()


def set_correlation_id(cid: str) -> None:
    """Set the correlation ID for the current request."""
    correlation_id_var.set(cid)


def log_prefix() -> str:
    """Get a log prefix with the correlation ID, or empty string if none."""
    cid = get_correlation_id()
    return f"[{cid}] " if cid else ""
