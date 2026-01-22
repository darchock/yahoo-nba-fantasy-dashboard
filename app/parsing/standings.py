"""
Parsing logic for Yahoo Fantasy standings data.

Converts raw Yahoo API responses into clean, structured data.
"""

from typing import Any

from app.parsing.helpers import safe_get, STAT_ID_TO_NAME_MAP


def parse_team_stats(stats_list: list) -> dict[str, Any]:
    """
    Parse team stats from Yahoo API stats list.

    Args:
        stats_list: List of stat objects from team_stats

    Returns:
        Dictionary mapping stat names to values
    """
    stats = {}
    for stat in stats_list:
        stat_id = str(stat.get("stat", {}).get("stat_id", ""))
        stat_value = stat.get("stat", {}).get("value", "")

        stat_name = STAT_ID_TO_NAME_MAP.get(stat_id)
        if stat_name:
            # Handle fraction stats (FGM/FGA, FTM/FTA)
            if "/" in stat_name:
                parts = stat_name.split("/")
                values = str(stat_value).split("/") if "/" in str(stat_value) else ["0", "0"]
                if len(values) >= 2 and len(parts) >= 2:
                    stats[parts[0]] = int(values[0]) if values[0] else 0
                    stats[parts[1]] = int(values[1]) if values[1] else 0
            else:
                try:
                    stats[stat_name] = float(stat_value) if stat_value else 0.0
                except (ValueError, TypeError):
                    stats[stat_name] = stat_value

    return stats


def parse_league_info(raw_data: dict) -> dict[str, Any]:
    """
    Extract league metadata from standings/scoreboard response.

    Args:
        raw_data: Raw Yahoo API response

    Returns:
        Clean league info dictionary
    """
    league_list = safe_get(raw_data, "fantasy_content", "league", default=[])
    if not league_list:
        return {}

    league_info = league_list[0] if isinstance(league_list, list) else {}

    return {
        "name": league_info.get("name", "Unknown League"),
        "league_key": league_info.get("league_key", ""),
        "league_id": league_info.get("league_id", ""),
        "num_teams": int(league_info.get("num_teams", 0)),
        "current_week": int(league_info.get("current_week", 1)),
        "start_week": int(league_info.get("start_week", 1)),
        "end_week": int(league_info.get("end_week", 1)),
        "season": league_info.get("season", ""),
        "scoring_type": league_info.get("scoring_type", ""),
    }


def parse_standings(raw_data: dict) -> dict[str, Any]:
    """
    Parse standings data from Yahoo API response.

    Args:
        raw_data: Raw Yahoo API standings response

    Returns:
        Clean dictionary with league info and teams list
    """
    result = {
        "league": parse_league_info(raw_data),
        "teams": [],
    }

    standings_list = safe_get(raw_data, "fantasy_content", "league", default=[])

    if len(standings_list) <= 1:
        return result

    standings_info = safe_get(standings_list, 1, "standings", default=[])
    teams = safe_get(standings_info, 0, "teams", default={})
    team_count = teams.get("count", 0)

    for i in range(team_count):
        team_info = safe_get(teams, str(i), "team", default=[])
        if not team_info:
            continue

        # Extract team details from first element (list of dicts)
        team_details = team_info[0] if team_info else []

        # Get team name, key, and logo
        team_name = ""
        team_key = ""
        team_logo = ""

        for item in team_details:
            if isinstance(item, dict):
                if "name" in item:
                    team_name = item["name"]
                if "team_key" in item:
                    team_key = item["team_key"]
                if "team_logos" in item:
                    logos = item["team_logos"]
                    if logos and len(logos) > 0:
                        team_logo = logos[0].get("team_logo", {}).get("url", "")

        # Extract stats from team_stats
        team_stats = {}
        if len(team_info) > 1:
            stats_container = team_info[1]
            if isinstance(stats_container, dict) and "team_stats" in stats_container:
                stats_list = safe_get(stats_container, "team_stats", "stats", default=[])
                team_stats = parse_team_stats(stats_list)

        # Extract standings (may be in second or third element)
        team_standings = {}
        for elem in team_info[1:]:
            if isinstance(elem, dict) and "team_standings" in elem:
                team_standings = elem["team_standings"]
                break

        rank = team_standings.get("rank", "")
        record = team_standings.get("outcome_totals", {})
        wins = int(record.get("wins", 0))
        losses = int(record.get("losses", 0))
        ties = int(record.get("ties", 0))
        total_games = wins + losses + ties
        win_pct_raw = record.get("percentage", 0)

        # Use the percentage from API if available, otherwise calculate
        if win_pct_raw:
            win_pct = float(win_pct_raw) * 100
        else:
            win_pct = wins / max(total_games, 1) * 100

        result["teams"].append({
            "rank": int(rank) if rank else 0,
            "team_key": team_key,
            "team_name": team_name,
            "team_logo": team_logo,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "win_pct": round(win_pct, 2),
            "stats": team_stats,
        })

    # Sort by rank
    result["teams"].sort(key=lambda x: x["rank"])

    return result
