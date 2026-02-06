"""
Tests for cache_utils module.

Tests the lazy refresh caching logic with 6 AM Eastern daily boundary.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import pytz

from app.services.cache_utils import (
    get_refresh_boundary,
    should_refresh_cache,
    is_week_complete,
    get_cache_expiry_for_week,
)


class TestGetRefreshBoundary:
    """Tests for get_refresh_boundary function."""

    def test_after_6am_returns_today_6am(self):
        """When it's after 6 AM Eastern, return today's 6 AM."""
        eastern = pytz.timezone("America/New_York")
        # Mock time: 10 AM Eastern on Jan 15, 2025
        mock_now = eastern.localize(datetime(2025, 1, 15, 10, 0, 0))

        with patch("app.services.cache_utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now

            boundary = get_refresh_boundary()

            # Should be 6 AM Eastern on Jan 15
            expected = eastern.localize(datetime(2025, 1, 15, 6, 0, 0))
            assert boundary == expected

    def test_before_6am_returns_yesterday_6am(self):
        """When it's before 6 AM Eastern, return yesterday's 6 AM."""
        eastern = pytz.timezone("America/New_York")
        # Mock time: 3 AM Eastern on Jan 15, 2025
        mock_now = eastern.localize(datetime(2025, 1, 15, 3, 0, 0))

        with patch("app.services.cache_utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now

            boundary = get_refresh_boundary()

            # Should be 6 AM Eastern on Jan 14
            expected = eastern.localize(datetime(2025, 1, 14, 6, 0, 0))
            assert boundary == expected

    def test_exactly_6am_returns_today_6am(self):
        """When it's exactly 6 AM Eastern, return today's 6 AM."""
        eastern = pytz.timezone("America/New_York")
        # Mock time: exactly 6 AM Eastern on Jan 15, 2025
        mock_now = eastern.localize(datetime(2025, 1, 15, 6, 0, 0))

        with patch("app.services.cache_utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now

            boundary = get_refresh_boundary()

            # Should be 6 AM Eastern on Jan 15
            expected = eastern.localize(datetime(2025, 1, 15, 6, 0, 0))
            assert boundary == expected


class TestShouldRefreshCache:
    """Tests for should_refresh_cache function."""

    def test_fetched_before_boundary_returns_true(self):
        """Data fetched before today's 6 AM should be refreshed."""
        eastern = pytz.timezone("America/New_York")
        # Current time: 10 AM Eastern on Jan 15, 2025
        mock_now = eastern.localize(datetime(2025, 1, 15, 10, 0, 0))

        # Data fetched at 5 AM today (before 6 AM boundary)
        fetched_at = eastern.localize(datetime(2025, 1, 15, 5, 0, 0))

        with patch("app.services.cache_utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now

            result = should_refresh_cache(fetched_at)

            assert result is True

    def test_fetched_after_boundary_returns_false(self):
        """Data fetched after today's 6 AM should not be refreshed."""
        eastern = pytz.timezone("America/New_York")
        # Current time: 10 AM Eastern on Jan 15, 2025
        mock_now = eastern.localize(datetime(2025, 1, 15, 10, 0, 0))

        # Data fetched at 7 AM today (after 6 AM boundary)
        fetched_at = eastern.localize(datetime(2025, 1, 15, 7, 0, 0))

        with patch("app.services.cache_utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now

            result = should_refresh_cache(fetched_at)

            assert result is False

    def test_fetched_yesterday_before_todays_6am_returns_true(self):
        """Data fetched yesterday should be refreshed after today's 6 AM."""
        eastern = pytz.timezone("America/New_York")
        # Current time: 10 AM Eastern on Jan 15, 2025
        mock_now = eastern.localize(datetime(2025, 1, 15, 10, 0, 0))

        # Data fetched at 8 PM yesterday
        fetched_at = eastern.localize(datetime(2025, 1, 14, 20, 0, 0))

        with patch("app.services.cache_utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now

            result = should_refresh_cache(fetched_at)

            assert result is True

    def test_handles_naive_datetime_as_utc(self):
        """Naive datetimes should be treated as UTC."""
        eastern = pytz.timezone("America/New_York")
        # Current time: 10 AM Eastern on Jan 15, 2025 (3 PM UTC)
        mock_now = eastern.localize(datetime(2025, 1, 15, 10, 0, 0))

        # Data fetched at 10 AM UTC (naive) - which is 5 AM Eastern
        # This is before 6 AM boundary, so should refresh
        fetched_at_naive = datetime(2025, 1, 15, 10, 0, 0)

        with patch("app.services.cache_utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now

            result = should_refresh_cache(fetched_at_naive)

            assert result is True

    def test_early_morning_before_6am_uses_previous_day_boundary(self):
        """At 3 AM, data from 11 PM yesterday should not be refreshed."""
        eastern = pytz.timezone("America/New_York")
        # Current time: 3 AM Eastern on Jan 15, 2025
        mock_now = eastern.localize(datetime(2025, 1, 15, 3, 0, 0))

        # Data fetched at 11 PM on Jan 14 (after yesterday's 6 AM boundary)
        fetched_at = eastern.localize(datetime(2025, 1, 14, 23, 0, 0))

        with patch("app.services.cache_utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now

            result = should_refresh_cache(fetched_at)

            assert result is False


class TestIsWeekComplete:
    """Tests for is_week_complete function."""

    def test_past_week_is_complete(self):
        """Week 5 is complete when current week is 10."""
        assert is_week_complete(week=5, current_week=10) is True

    def test_current_week_is_not_complete(self):
        """Week 10 is not complete when current week is 10."""
        assert is_week_complete(week=10, current_week=10) is False

    def test_future_week_is_not_complete(self):
        """Week 15 is not complete when current week is 10."""
        assert is_week_complete(week=15, current_week=10) is False

    def test_week_1_not_complete_when_current(self):
        """Week 1 is not complete when current week is 1."""
        assert is_week_complete(week=1, current_week=1) is False


class TestCachedDataIsStale:
    """Tests for CachedData.is_stale property."""

    def test_complete_data_is_never_stale(self):
        """CachedData with is_complete=True should never be stale."""
        from app.database.models import CachedData

        old_fetch = datetime(2025, 1, 1, 0, 0, 0)
        cache = CachedData(
            league_key="test",
            data_type="test",
            json_data={},
            fetched_at=old_fetch,
            is_complete=True,
        )
        assert cache.is_stale is False

    def test_incomplete_old_data_is_stale(self):
        """CachedData with is_complete=False and old fetch should be stale."""
        from app.database.models import CachedData

        old_fetch = datetime(2025, 1, 1, 0, 0, 0)
        cache = CachedData(
            league_key="test",
            data_type="test",
            json_data={},
            fetched_at=old_fetch,
            is_complete=False,
        )
        assert cache.is_stale is True


class TestGetCacheExpiryForWeek:
    """Tests for get_cache_expiry_for_week function."""

    def test_always_returns_none_for_lazy_refresh(self):
        """Lazy refresh doesn't use expires_at, always returns None."""
        # Completed week
        assert get_cache_expiry_for_week(week=5, current_week=10) is None

        # Current week
        assert get_cache_expiry_for_week(week=10, current_week=10) is None

        # Season totals (no week)
        assert get_cache_expiry_for_week(week=None, current_week=10) is None
