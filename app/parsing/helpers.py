"""
Parsing helpers for Yahoo Fantasy API responses.
Adapted from Yahoo_NBA_Fantasy_Hub/parsing_responses/consts.py
"""

from typing import Any, Dict, List, Optional


# Stat ID -> readable name mapping
STAT_ID_TO_NAME_MAP = {
    "5": "FG%",
    "8": "FT%",
    "10": "3PTM",
    "12": "PTS",
    "15": "REB",
    "16": "AST",
    "17": "STL",
    "18": "BLK",
    "19": "TO",
    "9004003": "FGM/FGA",
    "9007006": "FTM/FTA",
}

# Reverse mapping
STAT_NAME_TO_ID_MAP = {v: k for k, v in STAT_ID_TO_NAME_MAP.items()}


def safe_get(d: Any, *keys, default: Any = None) -> Any:
    """
    Robust nested getter for Yahoo Fantasy API responses.

    Behavior summary:
      - If d is dict and key in d -> follow it.
      - If d is dict and key is int -> try str(key) as a dict key (handles "0","1" style).
      - If d is dict and key is str but not present -> search dict values for a dict containing key.
      - If d is list and key is int -> index the list.
      - If d is list and key is str -> search list elements for the first dict that contains key.
      - If a step can't be resolved -> return default.

    Args:
        d: The data structure to traverse (dict, list, or nested combination)
        *keys: Sequence of keys/indices to follow
        default: Value to return if path not found

    Returns:
        The value at the specified path, or default if not found
    """
    for key in keys:
        if d is None:
            return default

        # --- Case A: current node is a dict ---
        if isinstance(d, dict):
            # Direct hit
            if key in d:
                d = d[key]
                continue

            # If key is int but dict uses numeric-string indices
            if isinstance(key, int):
                sk = str(key)
                if sk in d:
                    d = d[sk]
                    continue

            # If key is a str but not present: search values for a dict that contains this key
            if isinstance(key, str):
                found = False
                for v in d.values():
                    # If a value is a dict and contains the key directly, use it
                    if isinstance(v, dict) and key in v:
                        d = v[key]
                        found = True
                        break
                    # If a value is a dict with numeric-string subkeys (like {"0": {...}}),
                    # check those inner dicts as well
                    if isinstance(v, dict):
                        for inner in v.values():
                            if isinstance(inner, dict) and key in inner:
                                d = inner[key]
                                found = True
                                break
                        if found:
                            break
                if found:
                    continue

            # Not found on this dict
            return default

        # --- Case B: current node is a list ---
        if isinstance(d, list):
            # If user asked numeric index
            if isinstance(key, int):
                if 0 <= key < len(d):
                    d = d[key]
                    continue
                else:
                    return default

            # If user asked for a string key: scan list elements for that key
            if isinstance(key, str):
                found = False
                for item in d:
                    if isinstance(item, dict) and key in item:
                        d = item[key]
                        found = True
                        break
                if found:
                    continue

                # As fallback, check dict elements which themselves have numeric-string keys
                for item in d:
                    if isinstance(item, dict):
                        for v in item.values():
                            if isinstance(v, dict) and key in v:
                                d = v[key]
                                found = True
                                break
                        if found:
                            break
                if found:
                    continue

                return default

        # Any other type cannot be traversed
        return default

    return d


def extract_from_list_of_dicts(lst: List, key: str) -> Optional[Any]:
    """
    Given a list like [{a:1}, {b:2}, ...], return the value for dict[key].

    Args:
        lst: List of dictionaries
        key: Key to search for

    Returns:
        The value if found, None otherwise
    """
    if not isinstance(lst, list):
        return None
    for item in lst:
        if isinstance(item, dict) and key in item:
            return item[key]
    return None


def get_stat_name(stat_id: str) -> str:
    """
    Get readable stat name from stat ID.

    Args:
        stat_id: The Yahoo stat ID

    Returns:
        Human-readable stat name, or the ID if not found
    """
    return STAT_ID_TO_NAME_MAP.get(str(stat_id), str(stat_id))


def extract_team_info(team_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract team information from Yahoo API team response.
    This replaces the hardcoded MANAGER_ID_TO_NAME_MAP.

    Args:
        team_data: Team data from Yahoo API

    Returns:
        Dictionary with team_key, team_id, name, manager info
    """
    team_list = safe_get(team_data, "team", 0, default=[])

    team_key = safe_get(team_list, "team_key", default="")
    team_id = safe_get(team_list, "team_id", default="")
    name = safe_get(team_list, "name", default="Unknown Team")

    # Extract manager info
    managers = safe_get(team_list, "managers", default=[])
    manager_name = ""
    if managers:
        manager = safe_get(managers, 0, "manager", default={})
        manager_name = safe_get(manager, "nickname", default="")

    return {
        "team_key": team_key,
        "team_id": team_id,
        "name": name,
        "manager_name": manager_name,
    }


def build_team_name_map(teams_data: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Build a mapping of team_id -> team_name from API response.
    This dynamically replaces the hardcoded MANAGER_ID_TO_NAME_MAP.

    Args:
        teams_data: List of team data from Yahoo API

    Returns:
        Dictionary mapping team_id to team_name
    """
    team_map = {}
    for team_data in teams_data:
        info = extract_team_info(team_data)
        if info["team_id"]:
            team_map[info["team_id"]] = info["name"]
    return team_map
