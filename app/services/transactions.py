"""
Transaction Service - Storage and retrieval of league transactions.

Handles:
- Storing new transactions (with deduplication)
- Querying transactions with filters
- Computing transaction statistics
- Sync metadata tracking (cooldown management)
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database.models import Transaction, TransactionPlayer, UserLeague
from app.logging_config import get_logger

logger = get_logger(__name__)

# Default cooldown for transaction sync (in minutes)
TRANSACTION_SYNC_COOLDOWN_MINUTES = 120  # 2 hours


class TransactionService:
    """Service for managing league transactions in the database."""

    def __init__(self, db: Session):
        """
        Initialize the transaction service.

        Args:
            db: Database session
        """
        self.db = db

    def get_latest_transaction_id(self, league_key: str) -> Optional[str]:
        """
        Get the highest transaction_id for a league.

        Args:
            league_key: Yahoo league key

        Returns:
            Latest transaction_id or None if no transactions exist
        """
        result = (
            self.db.query(Transaction.transaction_id)
            .filter(Transaction.league_key == league_key)
            .order_by(desc(Transaction.timestamp))
            .first()
        )
        return result[0] if result else None

    def get_existing_transaction_ids(self, league_key: str) -> set:
        """
        Get all existing transaction IDs for a league.

        Args:
            league_key: Yahoo league key

        Returns:
            Set of existing transaction IDs
        """
        results = (
            self.db.query(Transaction.transaction_id)
            .filter(Transaction.league_key == league_key)
            .all()
        )
        return {r[0] for r in results}

    def store_transactions(
        self, league_key: str, parsed_transactions: List[Dict[str, Any]]
    ) -> int:
        """
        Store new transactions, skip existing ones.

        Args:
            league_key: Yahoo league key
            parsed_transactions: List of parsed transaction dicts from parsing module

        Returns:
            Count of new transactions inserted
        """
        if not parsed_transactions:
            return 0

        # Get existing transaction IDs for deduplication
        existing_ids = self.get_existing_transaction_ids(league_key)

        new_count = 0

        for txn_data in parsed_transactions:
            txn_id = txn_data.get("transaction_id")
            if not txn_id or txn_id in existing_ids:
                continue

            # Create Transaction record
            transaction = Transaction(
                transaction_id=txn_id,
                league_key=league_key,
                type=txn_data.get("type", ""),
                status=txn_data.get("status", ""),
                timestamp=txn_data.get("timestamp", 0),
                transaction_date=txn_data.get("transaction_date"),
                trader_team_key=txn_data.get("trader_team_key"),
                tradee_team_key=txn_data.get("tradee_team_key"),
            )

            # Create TransactionPlayer records
            for player_data in txn_data.get("players", []):
                player = TransactionPlayer(
                    player_id=player_data.get("player_id", ""),
                    player_name=player_data.get("player_name", ""),
                    nba_team=player_data.get("nba_team"),
                    position=player_data.get("position"),
                    action_type=player_data.get("action_type", ""),
                    source_type=player_data.get("source_type"),
                    source_team_key=player_data.get("source_team_key") or None,
                    source_team_name=player_data.get("source_team_name") or None,
                    destination_type=player_data.get("destination_type"),
                    destination_team_key=player_data.get("destination_team_key") or None,
                    destination_team_name=player_data.get("destination_team_name") or None,
                )
                transaction.players.append(player)

            self.db.add(transaction)
            existing_ids.add(txn_id)  # Prevent duplicates within same batch
            new_count += 1

        self.db.commit()

        logger.info(
            f"Stored {new_count} new transactions for league {league_key}"
        )

        return new_count

    def get_transactions(
        self,
        league_key: str,
        team_key: Optional[str] = None,
        transaction_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Transaction]:
        """
        Query transactions with optional filters.

        Args:
            league_key: Yahoo league key
            team_key: Optional team key to filter by (source or destination)
            transaction_type: Optional transaction type filter (add, drop, trade, add/drop)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of Transaction objects with players loaded
        """
        query = (
            self.db.query(Transaction)
            .filter(Transaction.league_key == league_key)
        )

        if transaction_type:
            query = query.filter(Transaction.type == transaction_type)

        if team_key:
            # Filter by team involvement (either in transaction_player or trade parties)
            query = query.filter(
                (Transaction.trader_team_key == team_key)
                | (Transaction.tradee_team_key == team_key)
                | Transaction.players.any(
                    (TransactionPlayer.source_team_key == team_key)
                    | (TransactionPlayer.destination_team_key == team_key)
                )
            )

        query = query.order_by(desc(Transaction.timestamp))
        query = query.offset(offset).limit(limit)

        return query.all()

    def get_transaction_count(self, league_key: str) -> int:
        """
        Get total number of transactions for a league.

        Args:
            league_key: Yahoo league key

        Returns:
            Total transaction count
        """
        return (
            self.db.query(func.count(Transaction.id))
            .filter(Transaction.league_key == league_key)
            .scalar()
        ) or 0

    def get_manager_activity(self, league_key: str) -> List[Dict[str, Any]]:
        """
        Get transaction counts per team.

        Args:
            league_key: Yahoo league key

        Returns:
            List of dicts with team_key, adds, drops, trades
        """
        # Get all transactions for the league
        transactions = (
            self.db.query(Transaction)
            .filter(Transaction.league_key == league_key)
            .all()
        )

        team_stats: Dict[str, Dict[str, int]] = {}

        for txn in transactions:
            for player in txn.players:
                # Track adds
                if player.action_type == "add" and player.destination_team_name:
                    team_name = player.destination_team_name
                    if team_name not in team_stats:
                        team_stats[team_name] = {"adds": 0, "drops": 0, "trades": 0}
                    team_stats[team_name]["adds"] += 1

                # Track drops
                elif player.action_type == "drop" and player.source_team_name:
                    team_name = player.source_team_name
                    if team_name not in team_stats:
                        team_stats[team_name] = {"adds": 0, "drops": 0, "trades": 0}
                    team_stats[team_name]["drops"] += 1
                # Track trades
                elif player.action_type == "trade":
                    for name in [player.source_team_name, player.destination_team_name]:
                        if name:
                            if name not in team_stats:
                                team_stats[name] = {"adds": 0, "drops": 0, "trades": 0}
                            team_stats[name]["trades"] += 1
        # Convert to list and sort by total activity
        result = []
        for team_name, stats in team_stats.items():
            total = stats["adds"] + stats["drops"] + stats["trades"]
            result.append({
                "team_key": team_name,
                "adds": stats["adds"],
                "drops": stats["drops"],
                "trades": stats["trades"],
                "total": total,
            })

        result.sort(key=lambda x: x["total"], reverse=True)
        return result

    def get_most_added_players(
        self, league_key: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get most frequently added players.

        Args:
            league_key: Yahoo league key
            limit: Maximum number of results

        Returns:
            List of dicts with player info and add count
        """
        results = (
            self.db.query(
                TransactionPlayer.player_id,
                TransactionPlayer.player_name,
                TransactionPlayer.nba_team,
                TransactionPlayer.position,
                func.count(TransactionPlayer.id).label("add_count"),
            )
            .join(Transaction)
            .filter(
                Transaction.league_key == league_key,
                TransactionPlayer.action_type == "add",
            )
            .group_by(
                TransactionPlayer.player_id,
                TransactionPlayer.player_name,
                TransactionPlayer.nba_team,
                TransactionPlayer.position,
            )
            .order_by(desc("add_count"))
            .limit(limit)
            .all()
        )

        return [
            {
                "player_id": r.player_id,
                "player_name": r.player_name,
                "nba_team": r.nba_team,
                "position": r.position,
                "times_added": r.add_count,
            }
            for r in results
        ]

    def get_most_dropped_players(
        self, league_key: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get most frequently dropped players.

        Args:
            league_key: Yahoo league key
            limit: Maximum number of results

        Returns:
            List of dicts with player info and drop count
        """
        results = (
            self.db.query(
                TransactionPlayer.player_id,
                TransactionPlayer.player_name,
                TransactionPlayer.nba_team,
                TransactionPlayer.position,
                func.count(TransactionPlayer.id).label("drop_count"),
            )
            .join(Transaction)
            .filter(
                Transaction.league_key == league_key,
                TransactionPlayer.action_type == "drop",
            )
            .group_by(
                TransactionPlayer.player_id,
                TransactionPlayer.player_name,
                TransactionPlayer.nba_team,
                TransactionPlayer.position,
            )
            .order_by(desc("drop_count"))
            .limit(limit)
            .all()
        )

        return [
            {
                "player_id": r.player_id,
                "player_name": r.player_name,
                "nba_team": r.nba_team,
                "position": r.position,
                "times_dropped": r.drop_count,
            }
            for r in results
        ]

    def get_transaction_stats(self, league_key: str) -> Dict[str, Any]:
        """
        Get comprehensive transaction statistics for a league.

        Args:
            league_key: Yahoo league key

        Returns:
            Dictionary with various transaction statistics
        """
        return {
            "total_transactions": self.get_transaction_count(league_key),
            "manager_activity": self.get_manager_activity(league_key),
            "most_added": self.get_most_added_players(league_key),
            "most_dropped": self.get_most_dropped_players(league_key),
        }

    def get_last_sync_time(
        self, user_id: int, league_key: str
    ) -> Optional[datetime]:
        """
        Get the last transaction sync time for a user-league pair.

        Args:
            user_id: User ID
            league_key: Yahoo league key

        Returns:
            Last sync datetime (UTC) or None if never synced
        """
        user_league = (
            self.db.query(UserLeague)
            .filter(
                UserLeague.user_id == user_id,
                UserLeague.league_key == league_key,
            )
            .first()
        )

        if not user_league or not user_league.last_transaction_sync_at:
            return None

        # Ensure timezone awareness
        sync_time = user_league.last_transaction_sync_at
        if sync_time.tzinfo is None:
            sync_time = sync_time.replace(tzinfo=timezone.utc)

        return sync_time

    def get_league_last_sync_time(self, league_key: str) -> Optional[datetime]:
        """
        Get the most recent transaction sync time for a league (across ALL users).

        This is used for cooldown checking - if ANY user has synced recently,
        no one needs to sync again since transaction data is shared.

        Args:
            league_key: Yahoo league key

        Returns:
            Most recent sync datetime (UTC) or None if never synced by anyone
        """
        # Find the most recent sync across all users in this league
        result = (
            self.db.query(func.max(UserLeague.last_transaction_sync_at))
            .filter(
                UserLeague.league_key == league_key,
                UserLeague.last_transaction_sync_at.isnot(None),
            )
            .scalar()
        )

        if result is None:
            return None

        # Ensure timezone awareness
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)

        return result

    def update_last_sync_time(
        self, user_id: int, league_key: str
    ) -> bool:
        """
        Update the last transaction sync time to now.

        Args:
            user_id: User ID
            league_key: Yahoo league key

        Returns:
            True if updated, False if user-league not found
        """
        user_league = (
            self.db.query(UserLeague)
            .filter(
                UserLeague.user_id == user_id,
                UserLeague.league_key == league_key,
            )
            .first()
        )

        if not user_league:
            logger.warning(
                f"Cannot update sync time: UserLeague not found "
                f"user={user_id} league={league_key}"
            )
            return False

        user_league.last_transaction_sync_at = datetime.now(timezone.utc)
        self.db.commit()

        logger.debug(
            f"Updated last_transaction_sync_at: "
            f"user={user_id} league={league_key}"
        )
        return True

    def is_sync_on_cooldown(
        self,
        user_id: int,
        league_key: str,
        cooldown_minutes: int = TRANSACTION_SYNC_COOLDOWN_MINUTES,
    ) -> tuple[bool, Optional[int]]:
        """
        Check if transaction sync is on cooldown for this league.

        NOTE: This checks across ALL users in the league, not just the current user.
        Transaction data is shared across all users in a league, so if anyone
        has synced recently, no one else needs to sync again.

        Args:
            user_id: User ID (kept for API compatibility, but not used for cooldown check)
            league_key: Yahoo league key
            cooldown_minutes: Cooldown period in minutes

        Returns:
            Tuple of (is_on_cooldown, minutes_remaining)
            - (True, N) if on cooldown with N minutes remaining
            - (False, None) if not on cooldown (sync allowed)
        """
        # Check league-level sync time (most recent across ALL users)
        last_sync = self.get_league_last_sync_time(league_key)

        if last_sync is None:
            return False, None

        now = datetime.now(timezone.utc)
        elapsed = now - last_sync
        elapsed_minutes = elapsed.total_seconds() / 60

        if elapsed_minutes < cooldown_minutes:
            remaining = int(cooldown_minutes - elapsed_minutes)
            logger.debug(
                f"Sync on cooldown: league={league_key} "
                f"elapsed={elapsed_minutes:.1f}m remaining={remaining}m"
            )
            return True, remaining

        return False, None

    def get_sync_metadata(
        self, user_id: int, league_key: str
    ) -> Dict[str, Any]:
        """
        Get sync metadata for display in UI.

        Args:
            user_id: User ID
            league_key: Yahoo league key

        Returns:
            Dictionary with sync metadata:
            - last_sync_at: ISO timestamp of league-level last sync (for cooldown)
            - last_sync_ago_minutes: Minutes since league-level last sync
            - cooldown_active: Whether cooldown is active (league-level)
            - cooldown_remaining_minutes: Minutes until sync allowed
            - user_last_sync_at: ISO timestamp of this user's last sync (for display)
        """
        # Get league-level sync time (for cooldown calculation)
        league_last_sync = self.get_league_last_sync_time(league_key)

        # Also get user's personal sync time (for display)
        user_last_sync = self.get_last_sync_time(user_id, league_key)

        # Check cooldown based on league-level sync
        on_cooldown, remaining = self.is_sync_on_cooldown(user_id, league_key)

        # Use league-level sync for display (since that's what matters for cooldown)
        if league_last_sync is None:
            return {
                "last_sync_at": None,
                "last_sync_ago_minutes": None,
                "cooldown_active": False,
                "cooldown_remaining_minutes": None,
                "user_last_sync_at": user_last_sync.isoformat() if user_last_sync else None,
            }

        now = datetime.now(timezone.utc)
        elapsed = now - league_last_sync
        elapsed_minutes = int(elapsed.total_seconds() / 60)

        return {
            "last_sync_at": league_last_sync.isoformat(),
            "last_sync_ago_minutes": elapsed_minutes,
            "cooldown_active": on_cooldown,
            "cooldown_remaining_minutes": remaining,
            "user_last_sync_at": user_last_sync.isoformat() if user_last_sync else None,
        }
