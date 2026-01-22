"""
Parsing logic for Yahoo Fantasy scoreboard/matchup data.

Converts raw Yahoo API responses into clean, structured data.
"""

from typing import Any

from app.parsing.helpers import safe_get, STAT_ID_TO_NAME_MAP
from app.parsing.standings import parse_team_stats, parse_league_info


# Stats where lower is better
LOWER_IS_BETTER = {"TO"}

# Ordered stat categories for display
STAT_CATEGORIES = ["FG%", "FT%", "3PTM", "PTS", "REB", "AST", "STL", "BLK", "TO"]


def parse_team_from_matchup(team_data: list) -> dict[str, Any]:
    """
    Parse a single team's data from a matchup.

    Args:
        team_data: Team data list from matchup

    Returns:
        Dictionary with team info and stats
    """
    team_details = team_data[0] if team_data else []

    # Extract team info
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

    # Extract stats
    team_stats = {}
    for elem in team_data[1:]:
        if isinstance(elem, dict) and "team_stats" in elem:
            stats_list = safe_get(elem, "team_stats", "stats", default=[])
            team_stats = parse_team_stats(stats_list)
            break

    # Extract win probability and points if available
    win_probability = None
    team_points = None
    for elem in team_data[1:]:
        if isinstance(elem, dict):
            if "win_probability" in elem:
                win_probability = float(elem["win_probability"])
            if "team_points" in elem:
                team_points = float(elem["team_points"].get("total", 0))

    return {
        "team_key": team_key,
        "team_name": team_name,
        "team_logo": team_logo,
        "stats": team_stats,
        "win_probability": win_probability,
        "team_points": team_points,
    }


def compare_stats(team1_stats: dict, team2_stats: dict) -> dict[str, Any]:
    """
    Compare stats between two teams to determine category winners.

    Args:
        team1_stats: Stats for team 1
        team2_stats: Stats for team 2

    Returns:
        Dictionary with comparison results for each stat category
    """
    comparison = {}

    for stat in STAT_CATEGORIES:
        val1 = team1_stats.get(stat, 0)
        val2 = team2_stats.get(stat, 0)

        # Handle non-numeric values
        if not isinstance(val1, (int, float)):
            val1 = 0
        if not isinstance(val2, (int, float)):
            val2 = 0

        # For turnovers, lower is better
        if stat in LOWER_IS_BETTER:
            if val1 < val2:
                winner = "team1"
            elif val2 < val1:
                winner = "team2"
            else:
                winner = "tie"
        else:
            # For all other stats, higher is better
            if val1 > val2:
                winner = "team1"
            elif val2 > val1:
                winner = "team2"
            else:
                winner = "tie"

        comparison[stat] = {
            "team1_value": val1,
            "team2_value": val2,
            "winner": winner,
        }

    return comparison


def parse_matchup(matchup_info: dict) -> dict[str, Any]:
    """
    Parse a single matchup.

    Args:
        matchup_info: Matchup data from Yahoo API

    Returns:
        Clean matchup dictionary
    """
    # Get matchup metadata
    week = matchup_info.get("week", "")
    is_playoffs = matchup_info.get("is_playoffs", "0") == "1"
    is_consolation = matchup_info.get("is_consolation", "0") == "1"
    status = matchup_info.get("status", "")
    is_tied = matchup_info.get("is_tied", "0") == "1"
    winner_team_key = matchup_info.get("winner_team_key", "")

    # Parse teams in this matchup
    teams_data = safe_get(matchup_info, "0", "teams", default={})
    team_count = teams_data.get("count", 0)

    teams = []
    for j in range(team_count):
        team_info = safe_get(teams_data, str(j), "team", default=[])
        if team_info:
            teams.append(parse_team_from_matchup(team_info))

    # Calculate stat comparison and scores
    stat_comparison = {}
    team1_wins = 0
    team2_wins = 0
    ties = 0

    if len(teams) >= 2:
        stat_comparison = compare_stats(
            teams[0].get("stats", {}),
            teams[1].get("stats", {})
        )
        for cat_result in stat_comparison.values():
            if cat_result["winner"] == "team1":
                team1_wins += 1
            elif cat_result["winner"] == "team2":
                team2_wins += 1
            else:
                ties += 1

    return {
        "week": int(week) if week else 0,
        "is_playoffs": is_playoffs,
        "is_consolation": is_consolation,
        "status": status,
        "is_tied": is_tied,
        "winner_team_key": winner_team_key,
        "teams": teams,
        "stat_comparison": stat_comparison,
        "score": {
            "team1_wins": team1_wins,
            "team2_wins": team2_wins,
            "ties": ties,
        },
    }


def parse_scoreboard(raw_data: dict) -> dict[str, Any]:
    """
    Parse scoreboard data from Yahoo API response.

    Args:
        raw_data: Raw Yahoo API scoreboard response

    Returns:
        Clean dictionary with league info and matchups list
    """
    result = {
        "league": parse_league_info(raw_data),
        "week": 0,
        "matchups": [],
    }

    league_list = safe_get(raw_data, "fantasy_content", "league", default=[])

    if len(league_list) <= 1:
        return result

    scoreboard_info = safe_get(league_list, 1, "scoreboard", default={})

    # Get the week from scoreboard
    result["week"] = int(scoreboard_info.get("week", 0))

    matchups_data = safe_get(scoreboard_info, "0", "matchups", default={})
    matchup_count = matchups_data.get("count", 0)

    for i in range(matchup_count):
        matchup_info = safe_get(matchups_data, str(i), "matchup", default={})
        if matchup_info:
            result["matchups"].append(parse_matchup(matchup_info))

    return result
