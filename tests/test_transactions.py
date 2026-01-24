"""
Tests for the transactions feature.

Tests cover:
- Transaction parsing
- Transaction service (storage and queries)
- Sync tracking (cooldown management)
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.parsing.transactions import (
    parse_player_from_transaction,
    parse_single_transaction,
    parse_transactions,
    get_transaction_summary,
)
from app.services.transactions import (
    TransactionService,
    TRANSACTION_SYNC_COOLDOWN_MINUTES,
)
from app.database.models import Transaction, TransactionPlayer, UserLeague, User


class TestTransactionParsing:
    """Tests for transaction parsing functions."""

    def test_parse_player_from_transaction_add(self):
        """Test parsing a player add from transaction data."""
        player_data = {
            "player": [
                [
                    {"player_key": "466.p.5317"},
                    {"player_id": "5317"},
                    {"name": {"full": "Marcus Smart", "first": "Marcus", "last": "Smart"}},
                    {"editorial_team_abbr": "LAL"},
                    {"display_position": "PG,SG"},
                ],
                {
                    "transaction_data": [
                        {
                            "type": "add",
                            "source_type": "freeagents",
                            "destination_type": "team",
                            "destination_team_key": "466.l.47711.t.10",
                            "destination_team_name": "Test Team",
                        }
                    ]
                },
            ]
        }

        result = parse_player_from_transaction(player_data)

        assert result["player_id"] == "5317"
        assert result["player_name"] == "Marcus Smart"
        assert result["nba_team"] == "LAL"
        assert result["position"] == "PG,SG"
        assert result["action_type"] == "add"
        assert result["source_type"] == "freeagents"
        assert result["destination_type"] == "team"
        assert result["destination_team_key"] == "466.l.47711.t.10"
        assert result["destination_team_name"] == "Test Team"

    def test_parse_player_from_transaction_drop(self):
        """Test parsing a player drop from transaction data."""
        player_data = {
            "player": [
                [
                    {"player_id": "10316"},
                    {"name": {"full": "Daniss Jenkins"}},
                    {"editorial_team_abbr": "DET"},
                    {"display_position": "PG,SG"},
                ],
                {
                    "transaction_data": {
                        "type": "drop",
                        "source_type": "team",
                        "source_team_key": "466.l.47711.t.10",
                        "source_team_name": "Drop Team",
                        "destination_type": "waivers",
                    }
                },
            ]
        }

        result = parse_player_from_transaction(player_data)

        assert result["player_id"] == "10316"
        assert result["player_name"] == "Daniss Jenkins"
        assert result["action_type"] == "drop"
        assert result["source_type"] == "team"
        assert result["source_team_key"] == "466.l.47711.t.10"
        assert result["source_team_name"] == "Drop Team"
        assert result["destination_type"] == "waivers"

    def test_parse_player_from_transaction_empty(self):
        """Test parsing empty player data returns empty dict."""
        result = parse_player_from_transaction({})
        assert result == {}

        result = parse_player_from_transaction({"player": []})
        assert result == {}

    def test_parse_single_transaction_add_drop(self):
        """Test parsing a combined add/drop transaction."""
        transaction_data = {
            "transaction": [
                {
                    "transaction_key": "466.l.47711.tr.564",
                    "transaction_id": "564",
                    "type": "add/drop",
                    "status": "successful",
                    "timestamp": "1768228688",
                },
                {
                    "players": {
                        "0": {
                            "player": [
                                [
                                    {"player_id": "5317"},
                                    {"name": {"full": "Marcus Smart"}},
                                    {"editorial_team_abbr": "LAL"},
                                ],
                                {
                                    "transaction_data": [
                                        {
                                            "type": "add",
                                            "source_type": "freeagents",
                                            "destination_type": "team",
                                            "destination_team_key": "466.l.47711.t.10",
                                        }
                                    ]
                                },
                            ]
                        },
                        "1": {
                            "player": [
                                [
                                    {"player_id": "10316"},
                                    {"name": {"full": "Daniss Jenkins"}},
                                    {"editorial_team_abbr": "DET"},
                                ],
                                {
                                    "transaction_data": {
                                        "type": "drop",
                                        "source_type": "team",
                                        "source_team_key": "466.l.47711.t.10",
                                        "destination_type": "waivers",
                                    }
                                },
                            ]
                        },
                        "count": 2,
                    }
                },
            ]
        }

        result = parse_single_transaction(transaction_data, "466.l.47711")

        assert result["transaction_id"] == "564"
        assert result["type"] == "add/drop"
        assert result["status"] == "successful"
        assert result["timestamp"] == 1768228688
        assert result["league_key"] == "466.l.47711"
        assert len(result["players"]) == 2
        assert result["players"][0]["action_type"] == "add"
        assert result["players"][1]["action_type"] == "drop"

    def test_parse_single_transaction_trade(self):
        """Test parsing a trade transaction."""
        transaction_data = {
            "transaction": [
                {
                    "transaction_id": "100",
                    "type": "trade",
                    "status": "successful",
                    "timestamp": "1700000000",
                    "trader_team_key": "466.l.47711.t.1",
                    "tradee_team_key": "466.l.47711.t.2",
                },
                {
                    "players": {
                        "count": 0,
                    }
                },
            ]
        }

        result = parse_single_transaction(transaction_data, "466.l.47711")

        assert result["transaction_id"] == "100"
        assert result["type"] == "trade"
        assert result["trader_team_key"] == "466.l.47711.t.1"
        assert result["tradee_team_key"] == "466.l.47711.t.2"

    def test_parse_single_transaction_empty(self):
        """Test parsing empty transaction returns empty dict."""
        result = parse_single_transaction({}, "test")
        assert result == {}

        result = parse_single_transaction({"transaction": []}, "test")
        assert result == {}

    def test_parse_transactions_full_response(self):
        """Test parsing a full Yahoo API transactions response."""
        raw_response = {
            "fantasy_content": {
                "league": [
                    {"league_key": "466.l.47711", "name": "Test League"},
                    {
                        "transactions": {
                            "0": {
                                "transaction": [
                                    {
                                        "transaction_id": "564",
                                        "type": "add/drop",
                                        "status": "successful",
                                        "timestamp": "1768228688",
                                    },
                                    {
                                        "players": {
                                            "0": {
                                                "player": [
                                                    [{"player_id": "5317"}, {"name": {"full": "Marcus Smart"}}],
                                                    {"transaction_data": [{"type": "add"}]},
                                                ]
                                            },
                                            "count": 1,
                                        }
                                    },
                                ]
                            },
                            "1": {
                                "transaction": [
                                    {
                                        "transaction_id": "563",
                                        "type": "add",
                                        "status": "successful",
                                        "timestamp": "1768217758",
                                    },
                                    {
                                        "players": {
                                            "0": {
                                                "player": [
                                                    [{"player_id": "5475"}, {"name": {"full": "Kelly Oubre Jr."}}],
                                                    {"transaction_data": [{"type": "add"}]},
                                                ]
                                            },
                                            "count": 1,
                                        }
                                    },
                                ]
                            },
                            "count": 2,
                        }
                    },
                ]
            }
        }

        result = parse_transactions(raw_response)

        assert len(result) == 2
        assert result[0]["transaction_id"] == "564"
        assert result[0]["league_key"] == "466.l.47711"
        assert result[1]["transaction_id"] == "563"

    def test_parse_transactions_empty_response(self):
        """Test parsing empty response returns empty list."""
        result = parse_transactions({})
        assert result == []

        result = parse_transactions({"fantasy_content": {"league": []}})
        assert result == []

    def test_get_transaction_summary(self):
        """Test generating transaction summary statistics."""
        transactions = [
            {
                "type": "add",
                "players": [
                    {"player_name": "Player A", "action_type": "add"},
                ],
            },
            {
                "type": "drop",
                "players": [
                    {"player_name": "Player B", "action_type": "drop"},
                ],
            },
            {
                "type": "add/drop",
                "players": [
                    {"player_name": "Player A", "action_type": "add"},
                    {"player_name": "Player C", "action_type": "drop"},
                ],
            },
        ]

        summary = get_transaction_summary(transactions)

        assert summary["total_transactions"] == 3
        assert summary["by_type"]["add"] == 1
        assert summary["by_type"]["drop"] == 1
        assert summary["by_type"]["add/drop"] == 1
        assert summary["most_added_players"]["Player A"] == 2
        assert summary["most_dropped_players"]["Player B"] == 1
        assert summary["most_dropped_players"]["Player C"] == 1


class TestTransactionService:
    """Tests for the TransactionService class."""

    @pytest.fixture
    def db_session(self):
        """Get a test database session."""
        from app.database.connection import get_db

        db = next(get_db())
        yield db
        db.close()

    @pytest.fixture
    def clean_test_transactions(self, db_session):
        """Clean up test transactions before and after tests."""
        # Clean up before test
        db_session.query(TransactionPlayer).filter(
            TransactionPlayer.transaction_id.in_(
                db_session.query(Transaction.id).filter(
                    Transaction.league_key.like("test_%")
                )
            )
        ).delete(synchronize_session=False)
        db_session.query(Transaction).filter(
            Transaction.league_key.like("test_%")
        ).delete(synchronize_session=False)
        db_session.commit()

        yield

        # Clean up after test
        db_session.query(TransactionPlayer).filter(
            TransactionPlayer.transaction_id.in_(
                db_session.query(Transaction.id).filter(
                    Transaction.league_key.like("test_%")
                )
            )
        ).delete(synchronize_session=False)
        db_session.query(Transaction).filter(
            Transaction.league_key.like("test_%")
        ).delete(synchronize_session=False)
        db_session.commit()

    def test_store_transactions_new(self, db_session, clean_test_transactions):
        """Test storing new transactions."""
        service = TransactionService(db_session)

        parsed_transactions = [
            {
                "transaction_id": "1001",
                "league_key": "test_league",
                "type": "add",
                "status": "successful",
                "timestamp": 1700000000,
                "transaction_date": datetime(2023, 11, 14, tzinfo=timezone.utc),
                "trader_team_key": None,
                "tradee_team_key": None,
                "players": [
                    {
                        "player_id": "p1",
                        "player_name": "Test Player 1",
                        "nba_team": "LAL",
                        "position": "PG",
                        "action_type": "add",
                        "source_type": "freeagents",
                        "source_team_key": None,
                        "destination_type": "team",
                        "destination_team_key": "test_league.t.1",
                    }
                ],
            }
        ]

        new_count = service.store_transactions("test_league", parsed_transactions)

        assert new_count == 1
        assert service.get_transaction_count("test_league") == 1

    def test_store_transactions_dedupe(self, db_session, clean_test_transactions):
        """Test that duplicate transactions are skipped."""
        service = TransactionService(db_session)

        parsed_transactions = [
            {
                "transaction_id": "2001",
                "league_key": "test_league_dedupe",
                "type": "add",
                "status": "successful",
                "timestamp": 1700000000,
                "transaction_date": datetime(2023, 11, 14, tzinfo=timezone.utc),
                "trader_team_key": None,
                "tradee_team_key": None,
                "players": [],
            }
        ]

        # First store
        new_count_1 = service.store_transactions("test_league_dedupe", parsed_transactions)
        assert new_count_1 == 1

        # Second store - should be deduplicated
        new_count_2 = service.store_transactions("test_league_dedupe", parsed_transactions)
        assert new_count_2 == 0
        assert service.get_transaction_count("test_league_dedupe") == 1

    def test_get_transactions_filter_by_type(self, db_session, clean_test_transactions):
        """Test filtering transactions by type."""
        service = TransactionService(db_session)

        parsed_transactions = [
            {
                "transaction_id": "3001",
                "league_key": "test_league_filter",
                "type": "add",
                "status": "successful",
                "timestamp": 1700000001,
                "transaction_date": datetime(2023, 11, 14, tzinfo=timezone.utc),
                "trader_team_key": None,
                "tradee_team_key": None,
                "players": [],
            },
            {
                "transaction_id": "3002",
                "league_key": "test_league_filter",
                "type": "drop",
                "status": "successful",
                "timestamp": 1700000002,
                "transaction_date": datetime(2023, 11, 14, tzinfo=timezone.utc),
                "trader_team_key": None,
                "tradee_team_key": None,
                "players": [],
            },
        ]

        service.store_transactions("test_league_filter", parsed_transactions)

        # Get only adds
        adds = service.get_transactions("test_league_filter", transaction_type="add")
        assert len(adds) == 1
        assert adds[0].type == "add"

        # Get only drops
        drops = service.get_transactions("test_league_filter", transaction_type="drop")
        assert len(drops) == 1
        assert drops[0].type == "drop"

    def test_get_most_added_players(self, db_session, clean_test_transactions):
        """Test getting most added players."""
        service = TransactionService(db_session)

        parsed_transactions = [
            {
                "transaction_id": "4001",
                "league_key": "test_league_added",
                "type": "add",
                "status": "successful",
                "timestamp": 1700000001,
                "transaction_date": datetime(2023, 11, 14, tzinfo=timezone.utc),
                "trader_team_key": None,
                "tradee_team_key": None,
                "players": [
                    {
                        "player_id": "p100",
                        "player_name": "Popular Player",
                        "nba_team": "LAL",
                        "position": "PG",
                        "action_type": "add",
                        "source_type": "freeagents",
                        "source_team_key": None,
                        "destination_type": "team",
                        "destination_team_key": "test_league_added.t.1",
                    }
                ],
            },
            {
                "transaction_id": "4002",
                "league_key": "test_league_added",
                "type": "add",
                "status": "successful",
                "timestamp": 1700000002,
                "transaction_date": datetime(2023, 11, 14, tzinfo=timezone.utc),
                "trader_team_key": None,
                "tradee_team_key": None,
                "players": [
                    {
                        "player_id": "p100",
                        "player_name": "Popular Player",
                        "nba_team": "LAL",
                        "position": "PG",
                        "action_type": "add",
                        "source_type": "waivers",
                        "source_team_key": None,
                        "destination_type": "team",
                        "destination_team_key": "test_league_added.t.2",
                    }
                ],
            },
        ]

        service.store_transactions("test_league_added", parsed_transactions)

        most_added = service.get_most_added_players("test_league_added")

        assert len(most_added) >= 1
        assert most_added[0]["player_name"] == "Popular Player"
        assert most_added[0]["times_added"] == 2

    def test_get_manager_activity(self, db_session, clean_test_transactions):
        """Test getting manager activity statistics."""
        service = TransactionService(db_session)

        parsed_transactions = [
            {
                "transaction_id": "5001",
                "league_key": "test_league_activity",
                "type": "add/drop",
                "status": "successful",
                "timestamp": 1700000001,
                "transaction_date": datetime(2023, 11, 14, tzinfo=timezone.utc),
                "trader_team_key": None,
                "tradee_team_key": None,
                "players": [
                    {
                        "player_id": "p1",
                        "player_name": "Player 1",
                        "nba_team": "LAL",
                        "position": "PG",
                        "action_type": "add",
                        "source_type": "freeagents",
                        "source_team_key": None,
                        "destination_type": "team",
                        "destination_team_key": "test_league_activity.t.1",
                    },
                    {
                        "player_id": "p2",
                        "player_name": "Player 2",
                        "nba_team": "BOS",
                        "position": "SG",
                        "action_type": "drop",
                        "source_type": "team",
                        "source_team_key": "test_league_activity.t.1",
                        "destination_type": "waivers",
                        "destination_team_key": None,
                    },
                ],
            },
        ]

        service.store_transactions("test_league_activity", parsed_transactions)

        activity = service.get_manager_activity("test_league_activity")

        assert len(activity) >= 1
        team1_activity = next(
            (a for a in activity if a["team_key"] == "test_league_activity.t.1"),
            None,
        )
        assert team1_activity is not None
        assert team1_activity["adds"] == 1
        assert team1_activity["drops"] == 1
        assert team1_activity["total"] == 2

    def test_get_transaction_stats(self, db_session, clean_test_transactions):
        """Test getting comprehensive transaction statistics."""
        service = TransactionService(db_session)

        parsed_transactions = [
            {
                "transaction_id": "6001",
                "league_key": "test_league_stats",
                "type": "add",
                "status": "successful",
                "timestamp": 1700000001,
                "transaction_date": datetime(2023, 11, 14, tzinfo=timezone.utc),
                "trader_team_key": None,
                "tradee_team_key": None,
                "players": [
                    {
                        "player_id": "p1",
                        "player_name": "Added Player",
                        "nba_team": "LAL",
                        "position": "PG",
                        "action_type": "add",
                        "source_type": "freeagents",
                        "source_team_key": None,
                        "destination_type": "team",
                        "destination_team_key": "test_league_stats.t.1",
                    }
                ],
            },
        ]

        service.store_transactions("test_league_stats", parsed_transactions)

        stats = service.get_transaction_stats("test_league_stats")

        assert stats["total_transactions"] == 1
        assert "manager_activity" in stats
        assert "most_added" in stats
        assert "most_dropped" in stats


class TestSyncTracking:
    """Tests for transaction sync tracking functionality."""

    @pytest.fixture
    def db_session(self):
        """Get a test database session."""
        from app.database.connection import get_db

        db = next(get_db())
        yield db
        db.close()

    @pytest.fixture
    def test_user(self, db_session):
        """Create a test user for sync tracking tests."""
        user = User(
            yahoo_guid="test_sync_user_guid",
            email="test@example.com",
            display_name="Test User",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        yield user
        # Cleanup
        db_session.delete(user)
        db_session.commit()

    @pytest.fixture
    def test_user_league(self, db_session, test_user):
        """Create a test user-league association."""
        user_league = UserLeague(
            user_id=test_user.id,
            league_key="test_sync_league_001",
            league_id="12345",
            league_name="Test Sync League",
        )
        db_session.add(user_league)
        db_session.commit()
        db_session.refresh(user_league)
        yield user_league
        # Cleanup
        db_session.delete(user_league)
        db_session.commit()

    def test_get_last_sync_time_never_synced(self, db_session, test_user, test_user_league):
        """Test getting last sync time when never synced."""
        service = TransactionService(db_session)

        last_sync = service.get_last_sync_time(test_user.id, test_user_league.league_key)

        assert last_sync is None

    def test_update_last_sync_time(self, db_session, test_user, test_user_league):
        """Test updating last sync time."""
        service = TransactionService(db_session)

        # Update sync time
        result = service.update_last_sync_time(test_user.id, test_user_league.league_key)

        assert result is True

        # Verify it was updated
        last_sync = service.get_last_sync_time(test_user.id, test_user_league.league_key)
        assert last_sync is not None
        assert isinstance(last_sync, datetime)
        # Should be very recent (within last minute)
        age = datetime.now(timezone.utc) - last_sync
        assert age.total_seconds() < 60

    def test_update_last_sync_time_nonexistent_league(self, db_session, test_user):
        """Test updating sync time for non-existent user-league."""
        service = TransactionService(db_session)

        result = service.update_last_sync_time(test_user.id, "nonexistent_league")

        assert result is False

    def test_is_sync_on_cooldown_never_synced(self, db_session, test_user, test_user_league):
        """Test cooldown check when never synced."""
        service = TransactionService(db_session)

        on_cooldown, remaining = service.is_sync_on_cooldown(
            test_user.id, test_user_league.league_key
        )

        assert on_cooldown is False
        assert remaining is None

    def test_is_sync_on_cooldown_recently_synced(self, db_session, test_user, test_user_league):
        """Test cooldown check when recently synced."""
        service = TransactionService(db_session)

        # Set sync time to now
        service.update_last_sync_time(test_user.id, test_user_league.league_key)

        on_cooldown, remaining = service.is_sync_on_cooldown(
            test_user.id, test_user_league.league_key
        )

        assert on_cooldown is True
        assert remaining is not None
        assert remaining > 0
        assert remaining <= TRANSACTION_SYNC_COOLDOWN_MINUTES

    def test_is_sync_on_cooldown_expired(self, db_session, test_user, test_user_league):
        """Test cooldown check when cooldown has expired."""
        service = TransactionService(db_session)

        # Set sync time to past (beyond cooldown)
        past_time = datetime.now(timezone.utc) - timedelta(
            minutes=TRANSACTION_SYNC_COOLDOWN_MINUTES + 10
        )
        test_user_league.last_transaction_sync_at = past_time
        db_session.commit()

        on_cooldown, remaining = service.is_sync_on_cooldown(
            test_user.id, test_user_league.league_key
        )

        assert on_cooldown is False
        assert remaining is None

    def test_get_sync_metadata_never_synced(self, db_session, test_user, test_user_league):
        """Test getting sync metadata when never synced."""
        service = TransactionService(db_session)

        metadata = service.get_sync_metadata(test_user.id, test_user_league.league_key)

        assert metadata["last_sync_at"] is None
        assert metadata["last_sync_ago_minutes"] is None
        assert metadata["cooldown_active"] is False
        assert metadata["cooldown_remaining_minutes"] is None

    def test_get_sync_metadata_recently_synced(self, db_session, test_user, test_user_league):
        """Test getting sync metadata when recently synced."""
        service = TransactionService(db_session)

        # Set sync time to 30 minutes ago
        past_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        test_user_league.last_transaction_sync_at = past_time
        db_session.commit()

        metadata = service.get_sync_metadata(test_user.id, test_user_league.league_key)

        assert metadata["last_sync_at"] is not None
        assert metadata["last_sync_ago_minutes"] is not None
        assert metadata["last_sync_ago_minutes"] >= 29  # Allow for slight timing differences
        assert metadata["last_sync_ago_minutes"] <= 31
        assert metadata["cooldown_active"] is True
        assert metadata["cooldown_remaining_minutes"] is not None
        assert metadata["cooldown_remaining_minutes"] > 0
