"""
Transactions page with manager activity and player movement analysis.

Displays transaction statistics from the database-backed API.
"""

from datetime import datetime, timezone

import streamlit as st
import httpx
import pandas as pd


# Dark-mode friendly highlight colors
COLOR_WIN = "#2d5a3d"  # Muted forest green
COLOR_LOSE = "#5a2d2d"  # Muted burgundy


def fetch_api_data(
    api_base_url: str,
    auth_token: str,
    endpoint: str,
    params: dict | None = None,
    verify_ssl: bool = False,
) -> dict | None:
    """
    Fetch data from an API endpoint.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        endpoint: API endpoint path
        params: Query parameters
        verify_ssl: Whether to verify SSL certificates

    Returns:
        Response data dict or None if error
    """
    try:
        headers = {"Authorization": f"Bearer {auth_token}"}

        with httpx.Client(
            base_url=api_base_url, headers=headers, verify=verify_ssl, timeout=30.0
        ) as client:
            response = client.get(endpoint, params=params or {})
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                st.error("Session expired. Please log in again.")
                return None
            else:
                st.error(f"Failed to fetch data: {response.status_code}")
                return None
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None


def render_manager_activity_tab(
    stats_data: dict | None,
    team_name_map: dict,
) -> None:
    """
    Render the Manager Activity tab showing transaction counts per team.

    Args:
        stats_data: Pre-fetched transaction stats data (from /transactions/stats)
        team_name_map: Mapping of team_key to team_name
    """
    if stats_data is None:
        return

    manager_activity = stats_data.get("manager_activity", [])

    if not manager_activity:
        st.info("No transaction activity found.")
        return

    st.caption("Showing transaction activity (adds, drops, trades) per team.")

    # Build table
    rows = []
    for entry in manager_activity:
        team_key = entry.get("team_key", "")
        team_name = team_name_map.get(team_key, team_key)
        rows.append({
            "Team": team_name,
            "Adds": entry.get("adds", 0),
            "Drops": entry.get("drops", 0),
            "Trades": entry.get("trades", 0),
            "Total": entry.get("total", 0),
        })

    df = pd.DataFrame(rows)

    # Highlight top and bottom totals
    if len(df) > 0:
        max_total = df["Total"].max()
        min_total = df["Total"].min()

        def style_total(val):
            if val == max_total:
                return f"background-color: {COLOR_WIN}; font-weight: bold"
            elif val == min_total and min_total != max_total:
                return f"background-color: {COLOR_LOSE}"
            return ""

        styled_df = df.style.applymap(style_total, subset=["Total"])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_most_added_tab(
    stats_data: dict | None,
) -> None:
    """
    Render the Most Added Players tab.

    Args:
        stats_data: Pre-fetched transaction stats data (from /transactions/stats)
    """
    if stats_data is None:
        return

    most_added = stats_data.get("most_added", [])

    if not most_added:
        st.info("No player add data found.")
        return

    st.caption("Players most frequently added across all teams.")

    rows = []
    for entry in most_added:
        rows.append({
            "Player": entry.get("player_name", "Unknown"),
            "Position": entry.get("position", "-"),
            "NBA Team": entry.get("nba_team", "-"),
            "Times Added": entry.get("times_added", 0),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_most_dropped_tab(
    stats_data: dict | None,
) -> None:
    """
    Render the Most Dropped Players tab.

    Args:
        stats_data: Pre-fetched transaction stats data (from /transactions/stats)
    """
    if stats_data is None:
        return

    most_dropped = stats_data.get("most_dropped", [])

    if not most_dropped:
        st.info("No player drop data found.")
        return

    st.caption("Players most frequently dropped across all teams.")

    rows = []
    for entry in most_dropped:
        rows.append({
            "Player": entry.get("player_name", "Unknown"),
            "Position": entry.get("position", "-"),
            "NBA Team": entry.get("nba_team", "-"),
            "Times Dropped": entry.get("times_dropped", 0),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_transactions_list(
    transactions: list,
    empty_message: str = "No transactions found.",
) -> None:
    """
    Render a list of transactions as a dataframe.

    Args:
        transactions: List of transaction dicts
        empty_message: Message to show if no transactions
    """
    if not transactions:
        st.info(empty_message)
        return

    # Build readable transaction list
    rows = []
    for txn in transactions:
        txn_date = txn.get("transaction_date", "")
        if txn_date:
            try:
                dt = datetime.fromisoformat(txn_date.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                date_str = txn_date[:16] if len(txn_date) > 16 else txn_date
        else:
            date_str = "-"

        txn_type = txn.get("type", "")
        players = txn.get("players", [])

        # Build description
        descriptions = []
        for p in players:
            action = p.get("action_type", "")
            player_name = p.get("player_name", "Unknown")

            # Use stored team names directly
            dest_team = p.get("destination_team_name") or ""
            src_team = p.get("source_team_name") or ""

            if action == "add":
                descriptions.append(f"{dest_team} added {player_name}")
            elif action == "drop":
                descriptions.append(f"{src_team} dropped {player_name}")
            elif action == "trade":
                descriptions.append(f"{player_name} traded ({src_team} -> {dest_team})")

        description = "; ".join(descriptions) if descriptions else "-"

        rows.append({
            "Date": date_str,
            "Type": txn_type,
            "Description": description,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_recent_transactions_tab(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    verify_ssl: bool = False,
) -> None:
    """
    Render the Recent Transactions tab showing individual transactions.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        verify_ssl: Whether to verify SSL certificates
    """
    st.caption("Showing recent transactions across all teams. Gets updated daily at 6 AM Eastern.")
    
    result = fetch_api_data(
        api_base_url=api_base_url,
        auth_token=auth_token,
        endpoint=f"/api/league/{league_key}/transactions",
        params={"limit": 50},
        verify_ssl=verify_ssl,
    )

    if result is None:
        return

    transactions = result.get("transactions", [])
    render_transactions_list(
        transactions,
        empty_message="No transactions found.",
    )

    # Show pagination info
    total = result.get("total", 0)
    shown = len(transactions)
    if shown < total:
        st.caption(f"Showing {shown} of {total} transactions")


def render_my_transactions_tab(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    user_team: dict | None,
    verify_ssl: bool = False,
) -> None:
    """
    Render the My Transactions tab showing only the current user's team transactions.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        user_team: User's team info dict (with team_key, name, etc.) or None
        verify_ssl: Whether to verify SSL certificates
    """
    if user_team is None:
        st.warning("Could not identify your team in this league.")
        return

    team_key = user_team.get("team_key")
    team_name = user_team.get("name", "Your Team")

    if not team_key:
        st.warning("Could not find your team key.")
        return

    st.caption(f"Showing transactions for: **{team_name}**")

    result = fetch_api_data(
        api_base_url=api_base_url,
        auth_token=auth_token,
        endpoint=f"/api/league/{league_key}/transactions",
        params={"team_key": team_key, "limit": 50},
        verify_ssl=verify_ssl,
    )

    if result is None:
        return

    transactions = result.get("transactions", [])
    render_transactions_list(
        transactions,
        empty_message=f"No transactions found for {team_name}.",
    )

    # Show pagination info
    total = result.get("total", 0)
    shown = len(transactions)
    if shown < total:
        st.caption(f"Showing {shown} of {total} transactions")


def fetch_team_name_map(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    verify_ssl: bool = False,
) -> dict:
    """
    Fetch team names from the API to build team_key -> team_name map.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        verify_ssl: Whether to verify SSL certificates

    Returns:
        Dictionary mapping team_key to team_name
    """
    result = fetch_api_data(
        api_base_url=api_base_url,
        auth_token=auth_token,
        endpoint=f"/api/league/{league_key}/teams",
        verify_ssl=verify_ssl,
    )

    if result is None:
        return {}

    team_map = {}
    teams = result.get("teams", [])
    for team in teams:
        team_key = team.get("team_key", "")
        team_name = team.get("name", team_key)
        if team_key:
            team_map[team_key] = team_name

    return team_map


def fetch_user_team(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    verify_ssl: bool = False,
) -> dict | None:
    """
    Fetch the current user's team in a league.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        verify_ssl: Whether to verify SSL certificates

    Returns:
        User's team info dict or None if not found
    """
    result = fetch_api_data(
        api_base_url=api_base_url,
        auth_token=auth_token,
        endpoint=f"/api/league/{league_key}/user/team",
        verify_ssl=verify_ssl,
    )

    if result is None:
        return None

    return result.get("team")


def render_transactions_page(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    verify_ssl: bool = False,
) -> None:
    """
    Render the transactions page with tabs for different views.

    Transactions are auto-synced using lazy refresh (6 AM Eastern boundary).

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        verify_ssl: Whether to verify SSL certificates
    """
    st.title("Transactions")

    # Fetch team name map for display
    team_name_map = fetch_team_name_map(
        api_base_url=api_base_url,
        auth_token=auth_token,
        league_key=league_key,
        verify_ssl=verify_ssl,
    )

    # Fetch user's team for "My Transactions" tab
    user_team = fetch_user_team(
        api_base_url=api_base_url,
        auth_token=auth_token,
        league_key=league_key,
        verify_ssl=verify_ssl,
    )

    # Fetch transaction stats once for all stats-related tabs
    # This avoids 3 separate API calls for Manager Activity, Most Added, Most Dropped
    stats_data = fetch_api_data(
        api_base_url=api_base_url,
        auth_token=auth_token,
        endpoint=f"/api/league/{league_key}/transactions/stats",
        verify_ssl=verify_ssl,
    )

    st.divider()

    # Content tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Recent Transactions",
        "My Transactions",
        "Manager Activity",
        "Most Added",
        "Most Dropped",
    ])

    with tab1:
        render_recent_transactions_tab(
            api_base_url=api_base_url,
            auth_token=auth_token,
            league_key=league_key,
            verify_ssl=verify_ssl,
        )

    with tab2:
        render_my_transactions_tab(
            api_base_url=api_base_url,
            auth_token=auth_token,
            league_key=league_key,
            user_team=user_team,
            verify_ssl=verify_ssl,
        )

    with tab3:
        render_manager_activity_tab(
            stats_data=stats_data,
            team_name_map=team_name_map,
        )

    with tab4:
        render_most_added_tab(stats_data=stats_data)

    with tab5:
        render_most_dropped_tab(stats_data=stats_data)
