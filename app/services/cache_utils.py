"""
Cache utility functions for lazy refresh caching.

This module provides functions for determining when cached data should be refreshed.
The strategy is "lazy refresh at 6 AM Eastern":
- First request after 6 AM Eastern: Fetch fresh data
- Subsequent requests same day: Use cache
- Completed weeks/matchups: Never re-fetch (cache forever)
"""

from datetime import datetime, timedelta
from typing import Optional

import pytz

from app.config import settings


def get_refresh_boundary() -> datetime:
    """
    Get the current refresh boundary (6 AM Eastern).

    The refresh boundary is 6 AM Eastern time. If the current time is before 6 AM,
    the boundary is yesterday's 6 AM. Otherwise, it's today's 6 AM.

    Returns:
        datetime: The refresh boundary in Eastern timezone
    """
    eastern = pytz.timezone(settings.CACHE_REFRESH_TIMEZONE)
    now_eastern = datetime.now(eastern)

    today_boundary = now_eastern.replace(
        hour=settings.CACHE_REFRESH_HOUR,
        minute=0,
        second=0,
        microsecond=0,
    )

    if now_eastern < today_boundary:
        # Before today's 6 AM, so boundary is yesterday's 6 AM
        return today_boundary - timedelta(days=1)
    else:
        # After today's 6 AM, so boundary is today's 6 AM
        return today_boundary


def should_refresh_cache(fetched_at: datetime) -> bool:
    """
    Determine if cached data should be refreshed.

    Returns True if the data was fetched BEFORE the current refresh boundary
    (6 AM Eastern today, or yesterday if before 6 AM).

    Args:
        fetched_at: When the data was originally fetched (can be naive or aware)

    Returns:
        True if the cache should be refreshed, False otherwise
    """
    eastern = pytz.timezone(settings.CACHE_REFRESH_TIMEZONE)

    # Handle timezone-naive datetimes (assume UTC)
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=pytz.UTC)

    # Convert to Eastern for comparison
    fetched_at_eastern = fetched_at.astimezone(eastern)

    refresh_boundary = get_refresh_boundary()

    return fetched_at_eastern < refresh_boundary


def is_week_complete(week: int, current_week: int) -> bool:
    """
    Determine if a week is complete based on the current week.

    A week is considered complete if it's before the current week.
    Completed weeks have final data that will never change.

    Args:
        week: The week to check
        current_week: The current week from the league

    Returns:
        True if the week is complete, False otherwise
    """
    return week < current_week


def get_cache_expiry_for_week(
    week: Optional[int],
    current_week: Optional[int],
) -> Optional[datetime]:
    """
    Calculate cache expiry based on week completion status.

    - Completed weeks (week < current_week): Never expire (returns None)
    - Current/future weeks or season totals: Return None (lazy refresh handles it)

    This function is primarily used to determine if data should be cached
    indefinitely (completed weeks) or use lazy refresh (current data).

    Args:
        week: The week being cached (None for season-level data)
        current_week: The current week from the league

    Returns:
        None (lazy refresh handles expiry via should_refresh_cache)
    """
    # For lazy refresh, we don't use expires_at anymore
    # The is_stale property will use should_refresh_cache instead
    return None
