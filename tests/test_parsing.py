"""
Tests for the parsing modules.
"""

import pytest

from app.parsing.helpers import safe_get, STAT_ID_TO_NAME_MAP, get_stat_name
from app.parsing.standings import parse_team_stats, parse_league_info, parse_standings
from app.parsing.scoreboard import (
    parse_team_from_matchup,
    compare_stats,
    parse_matchup,
    parse_scoreboard,
    STAT_CATEGORIES,
)


class TestHelpers:
    """Tests for parsing helpers."""

    def test_safe_get_simple_dict(self):
        """Test safe_get with simple dictionary."""
        data = {"a": {"b": {"c": 123}}}
        assert safe_get(data, "a", "b", "c") == 123

    def test_safe_get_missing_key(self):
        """Test safe_get returns default for missing key."""
        data = {"a": 1}
        assert safe_get(data, "b", default="missing") == "missing"

    def test_safe_get_numeric_string_keys(self):
        """Test safe_get handles Yahoo's numeric string keys."""
        data = {"0": {"team": "Lakers"}, "1": {"team": "Celtics"}}
        assert safe_get(data, 0, "team") == "Lakers"
        assert safe_get(data, 1, "team") == "Celtics"

    def test_safe_get_list_index(self):
        """Test safe_get handles list indexing."""
        data = {"teams": [{"name": "Team A"}, {"name": "Team B"}]}
        assert safe_get(data, "teams", 0, "name") == "Team A"
        assert safe_get(data, "teams", 1, "name") == "Team B"

    def test_safe_get_list_search(self):
        """Test safe_get searches list elements for key."""
        data = [{"name": "A"}, {"value": 123}]
        assert safe_get(data, "value") == 123

    def test_safe_get_none_data(self):
        """Test safe_get handles None data."""
        assert safe_get(None, "key", default="default") == "default"

    def test_stat_id_to_name_map(self):
        """Test stat ID mapping."""
        assert STAT_ID_TO_NAME_MAP["5"] == "FG%"
        assert STAT_ID_TO_NAME_MAP["12"] == "PTS"
        assert STAT_ID_TO_NAME_MAP["19"] == "TO"

    def test_get_stat_name(self):
        """Test get_stat_name function."""
        assert get_stat_name("5") == "FG%"
        assert get_stat_name("unknown") == "unknown"


class TestStandingsParsing:
    """Tests for standings parsing."""

    def test_parse_team_stats_basic(self):
        """Test parsing team stats with basic stats."""
        stats_list = [
            {"stat": {"stat_id": "12", "value": "1250"}},
            {"stat": {"stat_id": "15", "value": "500"}},
            {"stat": {"stat_id": "5", "value": ".485"}},
        ]
        result = parse_team_stats(stats_list)

        assert result["PTS"] == 1250.0
        assert result["REB"] == 500.0
        assert result["FG%"] == 0.485

    def test_parse_team_stats_fraction(self):
        """Test parsing fraction stats (FGM/FGA)."""
        stats_list = [
            {"stat": {"stat_id": "9004003", "value": "500/1000"}},
        ]
        result = parse_team_stats(stats_list)

        assert result["FGM"] == 500
        assert result["FGA"] == 1000

    def test_parse_team_stats_empty(self):
        """Test parsing empty stats list."""
        result = parse_team_stats([])
        assert result == {}

    def test_parse_league_info(self):
        """Test parsing league info from raw data."""
        raw_data = {
            "fantasy_content": {
                "league": [
                    {
                        "name": "Test League",
                        "league_key": "418.l.12345",
                        "num_teams": 10,
                        "current_week": 15,
                        "season": "2024",
                        "scoring_type": "head",
                    }
                ]
            }
        }
        result = parse_league_info(raw_data)

        assert result["name"] == "Test League"
        assert result["league_key"] == "418.l.12345"
        assert result["num_teams"] == 10
        assert result["current_week"] == 15
        assert result["season"] == "2024"

    def test_parse_league_info_empty(self):
        """Test parsing league info from empty data."""
        result = parse_league_info({})
        assert result == {}

    def test_parse_standings_basic(self):
        """Test parsing standings with basic data."""
        raw_data = {
            "fantasy_content": {
                "league": [
                    {"name": "Test League", "current_week": 10},
                    {
                        "standings": [
                            {
                                "teams": {
                                    "count": 2,
                                    "0": {
                                        "team": [
                                            [
                                                {"team_key": "418.l.12345.t.1"},
                                                {"name": "Team A"},
                                            ],
                                            {
                                                "team_standings": {
                                                    "rank": "1",
                                                    "outcome_totals": {
                                                        "wins": 50,
                                                        "losses": 30,
                                                        "ties": 0,
                                                        "percentage": ".625",
                                                    },
                                                }
                                            },
                                        ]
                                    },
                                    "1": {
                                        "team": [
                                            [
                                                {"team_key": "418.l.12345.t.2"},
                                                {"name": "Team B"},
                                            ],
                                            {
                                                "team_standings": {
                                                    "rank": "2",
                                                    "outcome_totals": {
                                                        "wins": 40,
                                                        "losses": 40,
                                                        "ties": 0,
                                                        "percentage": ".500",
                                                    },
                                                }
                                            },
                                        ]
                                    },
                                }
                            }
                        ]
                    },
                ]
            }
        }

        result = parse_standings(raw_data)

        assert result["league"]["name"] == "Test League"
        assert len(result["teams"]) == 2
        assert result["teams"][0]["team_name"] == "Team A"
        assert result["teams"][0]["rank"] == 1
        assert result["teams"][0]["wins"] == 50
        assert result["teams"][0]["win_pct"] == 62.5

    def test_parse_standings_empty(self):
        """Test parsing empty standings."""
        result = parse_standings({})
        assert result["league"] == {}
        assert result["teams"] == []


class TestScoreboardParsing:
    """Tests for scoreboard parsing."""

    def test_compare_stats_higher_is_better(self):
        """Test stat comparison where higher is better."""
        team1_stats = {"PTS": 100, "REB": 50}
        team2_stats = {"PTS": 80, "REB": 60}

        result = compare_stats(team1_stats, team2_stats)

        assert result["PTS"]["winner"] == "team1"
        assert result["REB"]["winner"] == "team2"

    def test_compare_stats_turnovers_lower_is_better(self):
        """Test that for turnovers, lower is better."""
        team1_stats = {"TO": 10}
        team2_stats = {"TO": 15}

        result = compare_stats(team1_stats, team2_stats)

        assert result["TO"]["winner"] == "team1"  # Lower is better

    def test_compare_stats_tie(self):
        """Test tie scenario."""
        team1_stats = {"PTS": 100}
        team2_stats = {"PTS": 100}

        result = compare_stats(team1_stats, team2_stats)

        assert result["PTS"]["winner"] == "tie"

    def test_compare_stats_missing_values(self):
        """Test comparison with missing stat values."""
        team1_stats = {"PTS": 100}
        team2_stats = {}

        result = compare_stats(team1_stats, team2_stats)

        assert result["PTS"]["winner"] == "team1"
        assert result["PTS"]["team1_value"] == 100
        assert result["PTS"]["team2_value"] == 0

    def test_stat_categories_order(self):
        """Test that stat categories are in expected order."""
        expected = ["FG%", "FT%", "3PTM", "PTS", "REB", "AST", "STL", "BLK", "TO"]
        assert STAT_CATEGORIES == expected

    def test_parse_matchup_basic(self):
        """Test parsing a basic matchup."""
        matchup_info = {
            "week": "15",
            "is_playoffs": "0",
            "status": "postevent",
            "0": {
                "teams": {
                    "count": 2,
                    "0": {
                        "team": [
                            [
                                {"team_key": "t.1"},
                                {"name": "Team A"},
                            ],
                            {
                                "team_stats": {
                                    "stats": [
                                        {"stat": {"stat_id": "12", "value": "100"}},
                                    ]
                                }
                            },
                        ]
                    },
                    "1": {
                        "team": [
                            [
                                {"team_key": "t.2"},
                                {"name": "Team B"},
                            ],
                            {
                                "team_stats": {
                                    "stats": [
                                        {"stat": {"stat_id": "12", "value": "90"}},
                                    ]
                                }
                            },
                        ]
                    },
                }
            },
        }

        result = parse_matchup(matchup_info)

        assert result["week"] == 15
        assert result["status"] == "postevent"
        assert len(result["teams"]) == 2
        assert result["teams"][0]["team_name"] == "Team A"
        assert result["teams"][1]["team_name"] == "Team B"
        assert "score" in result
        assert "stat_comparison" in result

    def test_parse_scoreboard_empty(self):
        """Test parsing empty scoreboard."""
        result = parse_scoreboard({})
        assert result["league"] == {}
        assert result["matchups"] == []


class TestCacheMetadata:
    """Tests for cache-related functionality."""

    def test_cache_duration_constant(self):
        """Test that cache duration is set appropriately."""
        from backend.routes.api import CACHE_DURATION_MINUTES
        assert CACHE_DURATION_MINUTES == 15

    def test_format_cache_metadata_none(self):
        """Test format_cache_metadata with None."""
        from backend.routes.api import format_cache_metadata

        result = format_cache_metadata(None)
        assert result["cached"] is False
        assert result["fetched_at"] is None


class TestSmartCaching:
    """Tests for smart caching with week completion awareness."""

    def test_is_week_complete_past_week(self):
        """Test that past weeks are identified as complete."""
        from backend.routes.api import is_week_complete

        # Week 10 when current week is 15 -> complete
        assert is_week_complete(week=10, current_week=15) is True
        # Week 1 when current week is 5 -> complete
        assert is_week_complete(week=1, current_week=5) is True

    def test_is_week_complete_current_week(self):
        """Test that current week is not complete."""
        from backend.routes.api import is_week_complete

        # Week 15 when current week is 15 -> not complete
        assert is_week_complete(week=15, current_week=15) is False

    def test_is_week_complete_future_week(self):
        """Test that future weeks are not complete."""
        from backend.routes.api import is_week_complete

        # Week 16 when current week is 15 -> not complete
        assert is_week_complete(week=16, current_week=15) is False

    def test_calculate_cache_expiry_completed_week(self):
        """Test that completed weeks get no expiry (None)."""
        from backend.routes.api import calculate_cache_expiry

        # Week 10 when current week is 15 -> None (never expires)
        result = calculate_cache_expiry(week=10, current_week=15)
        assert result is None

    def test_calculate_cache_expiry_current_week(self):
        """Test that current week gets standard TTL."""
        from datetime import datetime, timezone
        from backend.routes.api import calculate_cache_expiry, CACHE_DURATION_MINUTES

        # Week 15 when current week is 15 -> datetime in future
        result = calculate_cache_expiry(week=15, current_week=15)

        assert result is not None
        assert isinstance(result, datetime)
        # Should expire within the next CACHE_DURATION_MINUTES + 1 minute (to account for test timing)
        now = datetime.now(timezone.utc)
        diff_minutes = (result - now).total_seconds() / 60
        assert 0 < diff_minutes <= CACHE_DURATION_MINUTES + 1

    def test_calculate_cache_expiry_future_week(self):
        """Test that future weeks get standard TTL."""
        from datetime import datetime, timezone
        from backend.routes.api import calculate_cache_expiry, CACHE_DURATION_MINUTES

        # Week 17 when current week is 15 -> datetime in future
        result = calculate_cache_expiry(week=17, current_week=15)

        assert result is not None
        assert isinstance(result, datetime)
        now = datetime.now(timezone.utc)
        diff_minutes = (result - now).total_seconds() / 60
        assert 0 < diff_minutes <= CACHE_DURATION_MINUTES + 1

    def test_save_cached_data_with_default_expiry(self):
        """Test save_cached_data uses default TTL when not specified."""
        from datetime import datetime, timedelta, timezone
        from backend.routes.api import (
            save_cached_data,
            CACHE_DURATION_MINUTES,
            _USE_DEFAULT_TTL,
        )
        from app.database.connection import get_db
        from app.database.models import CachedData

        # Get a test database session
        db = next(get_db())
        try:
            # Save data with default TTL
            cache = save_cached_data(
                db=db,
                league_key="test_league_smart_cache_default",
                data_type="test_data",
                data={"test": "value"},
                week=1,
                expires_at=_USE_DEFAULT_TTL,
            )

            assert cache.expires_at is not None
            now = datetime.now(timezone.utc)
            # Should expire within CACHE_DURATION_MINUTES + 1 minute
            diff_minutes = (cache.expires_at.replace(tzinfo=timezone.utc) - now).total_seconds() / 60
            assert 0 < diff_minutes <= CACHE_DURATION_MINUTES + 1

            # Cleanup
            db.delete(cache)
            db.commit()
        finally:
            db.close()

    def test_save_cached_data_with_no_expiry(self):
        """Test save_cached_data sets no expiry when explicitly None."""
        from backend.routes.api import save_cached_data
        from app.database.connection import get_db

        # Get a test database session
        db = next(get_db())
        try:
            # Save data with no expiry (completed week)
            cache = save_cached_data(
                db=db,
                league_key="test_league_smart_cache_no_expiry",
                data_type="test_data",
                data={"test": "value"},
                week=5,
                expires_at=None,  # No expiry - completed week
            )

            assert cache.expires_at is None
            assert cache.is_stale is False  # Never stale

            # Cleanup
            db.delete(cache)
            db.commit()
        finally:
            db.close()

    def test_save_cached_data_with_custom_expiry(self):
        """Test save_cached_data accepts custom expiry datetime."""
        from datetime import datetime, timedelta, timezone
        from backend.routes.api import save_cached_data
        from app.database.connection import get_db

        # Get a test database session
        db = next(get_db())
        try:
            custom_expiry = datetime.now(timezone.utc) + timedelta(hours=2)

            # Save data with custom expiry
            cache = save_cached_data(
                db=db,
                league_key="test_league_smart_cache_custom",
                data_type="test_data",
                data={"test": "value"},
                week=10,
                expires_at=custom_expiry,
            )

            assert cache.expires_at is not None
            # Should be approximately 2 hours from now
            diff_hours = (cache.expires_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds() / 3600
            assert 1.9 < diff_hours < 2.1

            # Cleanup
            db.delete(cache)
            db.commit()
        finally:
            db.close()
