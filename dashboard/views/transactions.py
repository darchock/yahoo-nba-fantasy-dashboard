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
    api_base_url: str,
    auth_token: str,
    league_key: str,
    team_name_map: dict,
    verify_ssl: bool = False,
) -> None:
    """
    Render the Manager Activity tab showing transaction counts per team.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        team_name_map: Mapping of team_key to team_name
        verify_ssl: Whether to verify SSL certificates
    """
    result = fetch_api_data(
        api_base_url=api_base_url,
        auth_token=auth_token,
        endpoint=f"/api/league/{league_key}/transactions/stats",
        verify_ssl=verify_ssl,
    )

    if result is None:
        return

    manager_activity = result.get("manager_activity", [])

    if not manager_activity:
        st.info("No transaction activity found. Try syncing transactions first.")
        return

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
    api_base_url: str,
    auth_token: str,
    league_key: str,
    verify_ssl: bool = False,
) -> None:
    """
    Render the Most Added Players tab.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        verify_ssl: Whether to verify SSL certificates
    """
    result = fetch_api_data(
        api_base_url=api_base_url,
        auth_token=auth_token,
        endpoint=f"/api/league/{league_key}/transactions/stats",
        verify_ssl=verify_ssl,
    )

    if result is None:
        return

    most_added = result.get("most_added", [])

    if not most_added:
        st.info("No player add data found.")
        return

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
    api_base_url: str,
    auth_token: str,
    league_key: str,
    verify_ssl: bool = False,
) -> None:
    """
    Render the Most Dropped Players tab.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        verify_ssl: Whether to verify SSL certificates
    """
    result = fetch_api_data(
        api_base_url=api_base_url,
        auth_token=auth_token,
        endpoint=f"/api/league/{league_key}/transactions/stats",
        verify_ssl=verify_ssl,
    )

    if result is None:
        return

    most_dropped = result.get("most_dropped", [])

    if not most_dropped:
        st.info("No player drop data found.")
        return

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

    if not transactions:
        st.info("No transactions found. Click 'Sync Transactions' to fetch from Yahoo.")
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


def sync_transactions(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    force: bool = False,
    verify_ssl: bool = False,
) -> dict:
    """
    Trigger transaction sync with Yahoo API.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        force: If True, bypass cooldown
        verify_ssl: Whether to verify SSL certificates

    Returns:
        Dict with sync result including cooldown info
    """
    result = fetch_api_data(
        api_base_url=api_base_url,
        auth_token=auth_token,
        endpoint=f"/api/league/{league_key}/transactions/sync",
        params={"force": str(force).lower()},
        verify_ssl=verify_ssl,
    )

    if result is None:
        return {
            "success": False,
            "new_transactions": 0,
            "skipped": False,
            "cooldown_active": False,
        }

    return result


def fetch_sync_status(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    verify_ssl: bool = False,
) -> dict | None:
    """
    Fetch transaction sync status.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        verify_ssl: Whether to verify SSL certificates

    Returns:
        Sync status dict or None if error
    """
    return fetch_api_data(
        api_base_url=api_base_url,
        auth_token=auth_token,
        endpoint=f"/api/league/{league_key}/transactions/sync-status",
        verify_ssl=verify_ssl,
    )


def format_time_ago(minutes: int | None) -> str:
    """Format minutes as a human-readable time ago string."""
    if minutes is None:
        return "Never"
    if minutes < 1:
        return "Just now"
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def render_transactions_page(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    verify_ssl: bool = False,
) -> None:
    """
    Render the transactions page with tabs for different views.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        verify_ssl: Whether to verify SSL certificates
    """
    st.title("Transactions")

    # Fetch sync status
    sync_status = fetch_sync_status(
        api_base_url=api_base_url,
        auth_token=auth_token,
        league_key=league_key,
        verify_ssl=verify_ssl,
    )

    # Default values if status fetch fails
    cooldown_active = False
    cooldown_remaining = None
    last_sync_ago = None
    total_transactions = 0
    should_auto_sync = False

    if sync_status:
        cooldown_active = sync_status.get("cooldown_active", False)
        cooldown_remaining = sync_status.get("cooldown_remaining_minutes")
        last_sync_ago = sync_status.get("last_sync_ago_minutes")
        total_transactions = sync_status.get("total_transactions", 0)
        should_auto_sync = sync_status.get("should_auto_sync", False)

    # Auto-sync on page load if needed (no transactions or cooldown expired)
    # Use session state to prevent repeated auto-syncs on same page load
    auto_sync_key = f"auto_sync_{league_key}"
    if should_auto_sync and not st.session_state.get(auto_sync_key):
        st.session_state[auto_sync_key] = True
        with st.spinner("Syncing transactions from Yahoo..."):
            result = sync_transactions(
                api_base_url=api_base_url,
                auth_token=auth_token,
                league_key=league_key,
                verify_ssl=verify_ssl,
            )
            if result.get("success") and result.get("new_transactions", 0) > 0:
                st.toast(f"Synced {result['new_transactions']} new transactions!")
                st.rerun()

    # Sync button row with status
    col1, col2, col3 = st.columns([1, 2, 2])

    with col1:
        # Disable button if on cooldown
        button_disabled = cooldown_active
        button_label = "Sync Transactions"
        if cooldown_active and cooldown_remaining:
            button_label = f"Sync (wait {cooldown_remaining}m)"

        if st.button(button_label, type="primary", disabled=button_disabled):
            with st.spinner("Fetching from Yahoo..."):
                result = sync_transactions(
                    api_base_url=api_base_url,
                    auth_token=auth_token,
                    league_key=league_key,
                    verify_ssl=verify_ssl,
                )
                if result.get("success"):
                    new_count = result.get("new_transactions", 0)
                    if new_count > 0:
                        st.success(f"Added {new_count} new transactions!")
                    else:
                        st.info("No new transactions found.")
                    # Clear auto-sync flag to allow next auto-sync after cooldown
                    st.session_state[auto_sync_key] = False
                    st.rerun()

    with col2:
        # Show last sync time
        sync_time_str = format_time_ago(last_sync_ago)
        st.caption(f"Last sync: {sync_time_str}")

    with col3:
        # Show total transactions
        st.caption(f"Total: {total_transactions} transactions")

    # Fetch team name map for display
    team_name_map = fetch_team_name_map(
        api_base_url=api_base_url,
        auth_token=auth_token,
        league_key=league_key,
        verify_ssl=verify_ssl,
    )

    st.divider()

    # Content tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Recent Transactions",
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
        render_manager_activity_tab(
            api_base_url=api_base_url,
            auth_token=auth_token,
            league_key=league_key,
            team_name_map=team_name_map,
            verify_ssl=verify_ssl,
        )

    with tab3:
        render_most_added_tab(
            api_base_url=api_base_url,
            auth_token=auth_token,
            league_key=league_key,
            verify_ssl=verify_ssl,
        )

    with tab4:
        render_most_dropped_tab(
            api_base_url=api_base_url,
            auth_token=auth_token,
            league_key=league_key,
            verify_ssl=verify_ssl,
        )
