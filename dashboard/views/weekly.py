"""
Weekly page with scoreboard and matchup visualizations.

Displays weekly matchups from the clean API data.
"""

from datetime import datetime, timezone

import streamlit as st
import httpx
import pandas as pd


# Stat categories in display order
STAT_CATEGORIES = ["FG%", "FT%", "3PTM", "PTS", "REB", "AST", "STL", "BLK", "TO"]

# Dark-mode friendly highlight colors (muted/pastel)
COLOR_WIN = "#2d5a3d"  # Muted forest green
COLOR_LOSE = "#5a2d2d"  # Muted burgundy


def format_time_ago(iso_timestamp: str) -> str:
    """
    Format an ISO timestamp as a human-readable "time ago" string.

    Args:
        iso_timestamp: ISO format timestamp string

    Returns:
        Human-readable string like "5 minutes ago"
    """
    if not iso_timestamp:
        return "Unknown"

    try:
        fetched_time = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - fetched_time

        seconds = delta.total_seconds()
        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
    except Exception:
        return "Unknown"


def render_cache_indicator(cache_info: dict) -> None:
    """
    Render the cache freshness indicator.

    Args:
        cache_info: Cache metadata from API response
    """
    if cache_info.get("cached"):
        time_ago = format_time_ago(cache_info.get("fetched_at", ""))
        st.caption(f"Last updated: {time_ago}")
    else:
        st.caption("Freshly fetched")


def render_matchup_card(matchup: dict) -> None:
    """
    Render a single matchup as a card.

    Args:
        matchup: Parsed matchup data from API
    """
    teams = matchup.get("teams", [])
    if len(teams) < 2:
        st.warning("Incomplete matchup data")
        return

    team1 = teams[0]
    team2 = teams[1]
    score = matchup.get("score", {})
    stat_comparison = matchup.get("stat_comparison", {})

    team1_wins = score.get("team1_wins", 0)
    team2_wins = score.get("team2_wins", 0)
    ties = score.get("ties", 0)

    # Header with team names and score in same row
    team1_name = team1.get("team_name", "Team 1")
    team2_name = team2.get("team_name", "Team 2")

    # Build score display with ties if any
    ties_text = f" <span style='font-size: 0.7em; font-weight: normal'>({ties} ties)</span>" if ties > 0 else ""

    # Highlight winning team name
    if team1_wins > team2_wins:
        team1_style = "color: #6ecf6e"  # Soft green for winner
        team2_style = ""
    elif team2_wins > team1_wins:
        team1_style = ""
        team2_style = "color: #6ecf6e"  # Soft green for winner
    else:
        team1_style = ""
        team2_style = ""

    # Single row with team names and prominent score
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">
            <span style="font-size: 1.3em; font-weight: 500; {team1_style}">{team1_name}</span>
            <span style="font-size: 1.8em; font-weight: bold; margin: 0 1rem;">{team1_wins} - {team2_wins}{ties_text}</span>
            <span style="font-size: 1.3em; font-weight: 500; {team2_style}">{team2_name}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Stats comparison table
    rows = []
    for stat in STAT_CATEGORIES:
        comp = stat_comparison.get(stat, {})
        val1 = comp.get("team1_value", "-")
        val2 = comp.get("team2_value", "-")
        winner = comp.get("winner", "tie")

        # Format values
        if stat in ["FG%", "FT%"] and isinstance(val1, (int, float)):
            val1_str = f"{val1:.3f}"
        elif isinstance(val1, (int, float)):
            val1_str = f"{val1:.0f}" if val1 == int(val1) else f"{val1:.1f}"
        else:
            val1_str = str(val1)

        if stat in ["FG%", "FT%"] and isinstance(val2, (int, float)):
            val2_str = f"{val2:.3f}"
        elif isinstance(val2, (int, float)):
            val2_str = f"{val2:.0f}" if val2 == int(val2) else f"{val2:.1f}"
        else:
            val2_str = str(val2)

        rows.append({
            team1.get("team_name", "Team 1"): val1_str,
            "Category": stat,
            team2.get("team_name", "Team 2"): val2_str,
            "_winner": winner,
        })

    df = pd.DataFrame(rows)

    # Store winner info separately before dropping the column
    winner_map = df["_winner"].to_dict()

    # Display without the _winner column
    display_df = df.drop(columns=["_winner"])
    team1_col = team1.get("team_name", "Team 1")
    team2_col = team2.get("team_name", "Team 2")
    display_columns = list(display_df.columns)

    # Custom styling for winners (dark-mode friendly colors)
    def highlight_winners(row):
        winner = winner_map.get(row.name, "tie")
        styles = [""] * len(display_columns)

        if winner == "team1" and team1_col in display_columns:
            styles[display_columns.index(team1_col)] = f"background-color: {COLOR_WIN}; font-weight: bold"
        elif winner == "team2" and team2_col in display_columns:
            styles[display_columns.index(team2_col)] = f"background-color: {COLOR_WIN}; font-weight: bold"
        return styles

    styled_df = display_df.style.apply(highlight_winners, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)


def fetch_api_data(
    api_base_url: str,
    auth_token: str,
    endpoint: str,
    params: dict,
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

        with httpx.Client(base_url=api_base_url, headers=headers, verify=verify_ssl, timeout=30.0) as client:
            response = client.get(endpoint, params=params)
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


def render_totals_tab(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    week: int,
    verify_ssl: bool = False,
) -> None:
    """
    Render the totals table showing all teams' stats for the week.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        week: Week number
        verify_ssl: Whether to verify SSL certificates
    """
    result = fetch_api_data(
        api_base_url=api_base_url,
        auth_token=auth_token,
        endpoint=f"/api/league/{league_key}/weekly-totals",
        params={"week": week},
        verify_ssl=verify_ssl,
    )

    if result is None:
        return

    data = result.get("data", {})
    teams = data.get("teams", [])
    stat_categories = data.get("stat_categories", STAT_CATEGORIES)

    if not teams:
        st.info("No team data available.")
        return

    # Build table rows from pre-parsed data
    rows = []
    for team in teams:
        row = {"Team": team.get("team_name", "Unknown")}
        for stat in stat_categories:
            row[stat] = team.get(stat, "-")
        rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_rankings_tab(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    week: int,
    verify_ssl: bool = False,
) -> None:
    """
    Render the rankings table showing team ranks for each stat category.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        week: Week number
        verify_ssl: Whether to verify SSL certificates
    """
    result = fetch_api_data(
        api_base_url=api_base_url,
        auth_token=auth_token,
        endpoint=f"/api/league/{league_key}/weekly-rankings",
        params={"week": week},
        verify_ssl=verify_ssl,
    )

    if result is None:
        return

    data = result.get("data", {})
    teams = data.get("teams", [])
    stat_categories = data.get("stat_categories", STAT_CATEGORIES)
    num_teams = data.get("num_teams", len(teams))

    if not teams:
        st.info("No team data available.")
        return

    # Build table rows from pre-parsed data
    rows = []
    for team in teams:
        row = {"Team": team.get("team_name", "Unknown")}
        for stat in stat_categories:
            row[stat] = team.get(stat, "-")
        row["Avg Rank"] = team.get("avg_rank", "-")
        rows.append(row)

    df = pd.DataFrame(rows)

    # Style: highlight rank 1 in green, last rank in red (dark-mode friendly)
    def highlight_ranks(val):
        if val == 1:
            return f"background-color: {COLOR_WIN}; font-weight: bold"
        elif val == num_teams:
            return f"background-color: {COLOR_LOSE}"
        return ""

    styled_df = df.style.applymap(highlight_ranks, subset=stat_categories)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)


def render_h2h_tab(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    week: int,
    verify_ssl: bool = False,
) -> None:
    """
    Render the head-to-head matrix showing cross-league matchups.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        week: Week number
        verify_ssl: Whether to verify SSL certificates
    """
    result = fetch_api_data(
        api_base_url=api_base_url,
        auth_token=auth_token,
        endpoint=f"/api/league/{league_key}/weekly-h2h",
        params={"week": week},
        verify_ssl=verify_ssl,
    )

    if result is None:
        return

    data = result.get("data", {})
    team_names = data.get("team_names", [])
    matrix = data.get("matrix", [])
    totals = data.get("totals", [])

    if not team_names or not matrix:
        st.info("No team data available.")
        return

    # Build DataFrame for the matrix
    # Columns: team names + W-L-T + Win%
    columns = team_names + ["W-L-T", "Win%"]

    rows = []
    for i, team_name in enumerate(team_names):
        row_data = matrix[i] + [totals[i]["record"], totals[i]["win_pct"]]
        rows.append([team_name] + row_data)

    df = pd.DataFrame(rows, columns=["Team"] + columns)

    # Find the highest and lowest win% values
    win_pct_values = [t["win_pct"] for t in totals if isinstance(t.get("win_pct"), (int, float))]
    max_win_pct = max(win_pct_values) if win_pct_values else None
    min_win_pct = min(win_pct_values) if win_pct_values else None

    # Style only the first (highest) and last (lowest) win% managers
    def style_win_pct(val):
        if not isinstance(val, (int, float)):
            return ""
        if max_win_pct is not None and val == max_win_pct:
            return f"background-color: {COLOR_WIN}; font-weight: bold"
        elif min_win_pct is not None and val == min_win_pct:
            return f"background-color: {COLOR_LOSE}"
        return ""

    styled_df = df.style.applymap(style_win_pct, subset=["Win%"])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)


def fetch_scoreboard_data(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    week: int,
    verify_ssl: bool = False,
) -> tuple[list, dict] | None:
    """
    Fetch scoreboard data from the API.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        week: Week number to display
        verify_ssl: Whether to verify SSL certificates

    Returns:
        Tuple of (matchups list, cache_info dict) or None if error
    """
    try:
        headers = {"Authorization": f"Bearer {auth_token}"}
        params = {"week": week}

        with httpx.Client(base_url=api_base_url, headers=headers, verify=verify_ssl, timeout=30.0) as client:
            response = client.get(f"/api/league/{league_key}/scoreboard", params=params)
            if response.status_code == 200:
                response_data = response.json()
                data = response_data.get("data", {})
                cache_info = response_data.get("cache", {})
                matchups = data.get("matchups", [])
                return matchups, cache_info
            elif response.status_code == 401:
                st.error("Session expired. Please log in again.")
                return None
            else:
                st.error(f"Failed to fetch scoreboard: {response.status_code}")
                return None
    except Exception as e:
        st.error(f"Error fetching scoreboard: {e}")
        return None


def render_scoreboard_tab(matchups: list) -> None:
    """
    Render the scoreboard content.

    Args:
        matchups: List of matchup data from API
    """
    if not matchups:
        st.info("No matchups found for this week.")
        return

    # Render each matchup
    for i, matchup in enumerate(matchups):
        with st.container():
            render_matchup_card(matchup)

            # Add playoff/consolation badge if applicable
            badges = []
            if matchup.get("is_playoffs"):
                badges.append("Playoffs")
            if matchup.get("is_consolation"):
                badges.append("Consolation")
            if badges:
                st.caption(" | ".join(badges))

        if i < len(matchups) - 1:
            st.divider()

    # Summary table
    st.divider()
    st.subheader("Week Summary")

    summary_rows = []
    for matchup in matchups:
        teams = matchup.get("teams", [])
        score = matchup.get("score", {})
        if len(teams) >= 2:
            team1_wins = score.get("team1_wins", 0)
            team2_wins = score.get("team2_wins", 0)

            summary_rows.append({
                "Team 1": teams[0].get("team_name", "Unknown"),
                "Score": f"{team1_wins}-{team2_wins}",
                "Team 2": teams[1].get("team_name", "Unknown"),
                "Status": "Complete" if matchup.get("status") == "postevent" else "In Progress",
            })

    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)


def render_weekly_page(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    verify_ssl: bool = False,
) -> None:
    """
    Render the weekly page with week picker and content tabs.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        verify_ssl: Whether to verify SSL certificates
    """
    st.title("Weekly Analysis")

    # Week picker
    col1, col2, col3 = st.columns([1, 2, 2])
    with col1:
        week_options = list(range(1, 20))  # Weeks 1-19 (regular season)
        week = st.selectbox(
            "Select Week",
            options=week_options,
            index=None,
            placeholder="Choose a week...",
            key="week_picker",
        )
    with col2:
        if week == 19:
            st.caption("End of Regular Season")

    if week is None:
        st.info("Select a week above to view data.")
        return

    # Fetch data once for all tabs
    result = fetch_scoreboard_data(
        api_base_url=api_base_url,
        auth_token=auth_token,
        league_key=league_key,
        week=week,
        verify_ssl=verify_ssl,
    )

    if result is None:
        return

    matchups, cache_info = result

    # Cache indicator
    render_cache_indicator(cache_info)

    st.divider()

    # Content tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Scoreboard", "Totals", "Rankings", "Head-to-Head"])

    with tab1:
        render_scoreboard_tab(matchups)

    with tab2:
        render_totals_tab(
            api_base_url=api_base_url,
            auth_token=auth_token,
            league_key=league_key,
            week=week,
            verify_ssl=verify_ssl,
        )

    with tab3:
        render_rankings_tab(
            api_base_url=api_base_url,
            auth_token=auth_token,
            league_key=league_key,
            week=week,
            verify_ssl=verify_ssl,
        )

    with tab4:
        render_h2h_tab(
            api_base_url=api_base_url,
            auth_token=auth_token,
            league_key=league_key,
            week=week,
            verify_ssl=verify_ssl,
        )
