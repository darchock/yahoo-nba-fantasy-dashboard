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

    # Header with team names and score
    col1, col2, col3 = st.columns([2, 1, 2])

    with col1:
        if team1_wins > team2_wins:
            st.markdown(f"### :green[{team1.get('team_name', 'Team 1')}]")
        else:
            st.markdown(f"### {team1.get('team_name', 'Team 1')}")

    with col2:
        score_display = f"**{team1_wins}** - **{team2_wins}**"
        if ties > 0:
            score_display += f" ({ties} ties)"
        st.markdown(f"<div style='text-align: center'>{score_display}</div>", unsafe_allow_html=True)

    with col3:
        if team2_wins > team1_wins:
            st.markdown(f"### :green[{team2.get('team_name', 'Team 2')}]")
        else:
            st.markdown(f"### {team2.get('team_name', 'Team 2')}")

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

    # Custom styling for winners
    def highlight_winners(row):
        winner = winner_map.get(row.name, "tie")
        styles = [""] * len(display_columns)

        if winner == "team1" and team1_col in display_columns:
            styles[display_columns.index(team1_col)] = "background-color: #d4edda; font-weight: bold"
        elif winner == "team2" and team2_col in display_columns:
            styles[display_columns.index(team2_col)] = "background-color: #d4edda; font-weight: bold"
        return styles

    styled_df = display_df.style.apply(highlight_winners, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)


def render_scoreboard_tab(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    week: int,
    verify_ssl: bool = False,
) -> None:
    """
    Render the scoreboard content.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        week: Week number to display
        verify_ssl: Whether to verify SSL certificates
    """
    # Fetch scoreboard data from API
    response_data = None
    try:
        headers = {"Authorization": f"Bearer {auth_token}"}
        params = {"week": week}

        with httpx.Client(base_url=api_base_url, headers=headers, verify=verify_ssl, timeout=30.0) as client:
            response = client.get(f"/api/league/{league_key}/scoreboard", params=params)
            if response.status_code == 200:
                response_data = response.json()
            elif response.status_code == 401:
                st.error("Session expired. Please log in again.")
                return
            else:
                st.error(f"Failed to fetch scoreboard: {response.status_code}")
                return
    except Exception as e:
        st.error(f"Error fetching scoreboard: {e}")
        return

    # Extract data and cache info
    data = response_data.get("data", {})
    cache_info = response_data.get("cache", {})
    matchups = data.get("matchups", [])

    # Cache indicator
    render_cache_indicator(cache_info)

    if not matchups:
        st.info("No matchups found for this week.")
        return

    st.divider()

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
        st.info("Select a week above to view the scoreboard.")
        return

    st.divider()

    # Content tabs
    tab1, tab2 = st.tabs(["Scoreboard", "Visualizations"])

    with tab1:
        render_scoreboard_tab(
            api_base_url=api_base_url,
            auth_token=auth_token,
            league_key=league_key,
            week=week,
            verify_ssl=verify_ssl,
        )

    with tab2:
        st.info("Weekly visualizations coming soon...")
        st.markdown("""
        **Planned features:**
        - Category performance charts
        - Week-over-week trends
        - Team comparison radar charts
        """)
