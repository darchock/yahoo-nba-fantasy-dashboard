"""
Transaction Service - Storage and retrieval of league transactions.

Handles:
- Storing new transactions (with deduplication)
- Querying transactions with filters
- Computing transaction statistics
"""

from typing import Dict, List, Optional, Any

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database.models import Transaction, TransactionPlayer
from app.logging_config import get_logger

logger = get_logger(__name__)


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
