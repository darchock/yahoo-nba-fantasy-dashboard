"""
Parse transaction responses from Yahoo Fantasy API.

Handles league-wide transaction responses.
Extracts: transaction type, timestamp, players involved, source/destination info.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.parsing.helpers import safe_get, extract_from_list_of_dicts


def parse_player_from_transaction(player_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a single player entry from a transaction.

    Args:
        player_data: Raw player data from Yahoo API

    Returns:
        Dictionary with player info and transaction details
    """
    player_info = player_data.get("player", [])

    if not player_info or len(player_info) < 2:
        return {}

    # First element is a list of player attributes
    player_attrs = player_info[0] if isinstance(player_info[0], list) else []

    player_id = extract_from_list_of_dicts(player_attrs, "player_id")
    name_dict = extract_from_list_of_dicts(player_attrs, "name") or {}
    player_name = name_dict.get("full", "") if isinstance(name_dict, dict) else ""
    nba_team = extract_from_list_of_dicts(player_attrs, "editorial_team_abbr") or ""
    position = extract_from_list_of_dicts(player_attrs, "display_position") or ""

    # Second element contains transaction_data
    transaction_data_wrapper = player_info[1] if len(player_info) > 1 else {}
    transaction_data = transaction_data_wrapper.get("transaction_data", {})

    # transaction_data can be a dict or a list with one dict
    if isinstance(transaction_data, list) and len(transaction_data) > 0:
        transaction_data = transaction_data[0]

    # Ensure transaction_data is a dict before calling .get()
    if not isinstance(transaction_data, dict):
        transaction_data = {}

    return {
        "player_id": player_id or "",
        "player_name": player_name,
        "nba_team": nba_team,
        "position": position,
        "action_type": transaction_data.get("type", ""),
        "source_type": transaction_data.get("source_type", ""),
        "source_team_key": transaction_data.get("source_team_key", ""),
        "source_team_name": transaction_data.get("source_team_name", ""),
        "destination_type": transaction_data.get("destination_type", ""),
        "destination_team_key": transaction_data.get("destination_team_key", ""),
        "destination_team_name": transaction_data.get("destination_team_name", ""),
    }


def parse_single_transaction(
    transaction_data: Dict[str, Any], league_key: str
) -> Dict[str, Any]:
    """
    Parse a single transaction entry.

    Args:
        transaction_data: Raw transaction data from Yahoo API
        league_key: League key for reference

    Returns:
        Parsed transaction dictionary
    """
    transaction_list = transaction_data.get("transaction", [])

    if not transaction_list or len(transaction_list) < 2:
        return {}

    # First element contains transaction metadata
    meta = transaction_list[0]
    transaction_id = meta.get("transaction_id", "")
    transaction_type = meta.get("type", "")
    status = meta.get("status", "")
    timestamp_raw = meta.get("timestamp", "")

    # Convert timestamp to datetime
    try:
        timestamp_int = int(timestamp_raw)
        transaction_date = datetime.fromtimestamp(timestamp_int, tz=timezone.utc)
    except (ValueError, TypeError):
        timestamp_int = 0
        transaction_date = datetime.now(timezone.utc)

    # Trade-specific fields (team keys not names)
    trader_team_key = meta.get("trader_team_key", "")
    tradee_team_key = meta.get("tradee_team_key", "")

    # Second element contains players
    players_wrapper = transaction_list[1]
    players_dict = players_wrapper.get("players", {})

    players = []
    player_count = players_dict.get("count", 0)

    for i in range(player_count):
        player_data = players_dict.get(str(i), {})
        if player_data:
            parsed_player = parse_player_from_transaction(player_data)
            if parsed_player and parsed_player.get("player_id"):
                players.append(parsed_player)

    return {
        "transaction_id": transaction_id,
        "league_key": league_key,
        "type": transaction_type,
        "status": status,
        "timestamp": timestamp_int,
        "transaction_date": transaction_date,
        "trader_team_key": trader_team_key or None,
        "tradee_team_key": tradee_team_key or None,
        "players": players,
    }


def parse_transactions(raw_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse raw Yahoo API response into list of transaction dicts.

    Args:
        raw_response: Raw JSON response from /league/{key}/transactions endpoint

    Returns:
        List of parsed transaction dictionaries
    """
    result = []

    try:
        league_data = safe_get(raw_response, "fantasy_content", "league")

        if not isinstance(league_data, list) or len(league_data) < 2:
            return result

        # Extract league key from the first element
        league_info = league_data[0] if isinstance(league_data[0], dict) else {}
        league_key = league_info.get("league_key", "")

        transactions_wrapper = league_data[1]
        transactions_dict = transactions_wrapper.get("transactions", {})

        transaction_count = transactions_dict.get("count", 0)

        for i in range(transaction_count):
            transaction_data = transactions_dict.get(str(i), {})
            if transaction_data:
                parsed = parse_single_transaction(transaction_data, league_key)
                if parsed and parsed.get("transaction_id"):
                    result.append(parsed)

    except Exception:
        pass

    return result


def get_transaction_summary(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate summary statistics from parsed transactions.

    Args:
        transactions: List of parsed transaction dictionaries

    Returns:
        Summary dictionary with counts and breakdowns
    """
    summary: Dict[str, Any] = {
        "total_transactions": len(transactions),
        "by_type": {"add": 0, "drop": 0, "add/drop": 0, "trade": 0},
        "most_added_players": {},
        "most_dropped_players": {},
    }

    for txn in transactions:
        txn_type = txn.get("type", "")
        if txn_type in summary["by_type"]:
            summary["by_type"][txn_type] += 1

        for player in txn.get("players", []):
            player_name = player.get("player_name", "Unknown")
            action = player.get("action_type", "")

            if action == "add":
                summary["most_added_players"][player_name] = (
                    summary["most_added_players"].get(player_name, 0) + 1
                )
            elif action == "drop":
                summary["most_dropped_players"][player_name] = (
                    summary["most_dropped_players"].get(player_name, 0) + 1
                )

    return summary
