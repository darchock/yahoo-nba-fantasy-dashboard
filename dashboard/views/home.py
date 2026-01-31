"""
Home page with league overview.

Displays standings and league information from the clean API data.
"""

from datetime import datetime, timezone

import streamlit as st
import httpx
import pandas as pd


# Stat categories in display order
STAT_CATEGORIES = ["FG%", "FT%", "3PTM", "PTS", "REB", "AST", "STL", "BLK", "TO"]

# Stats where lower is better (for ranking calculation)
LOWER_IS_BETTER = ["TO"]

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
        # Parse the ISO timestamp
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
        time_ago = format_time_ago(cache_info.get("fetched_at"))
        st.caption(f"Last updated: {time_ago}")
    else:
        st.caption("Freshly fetched")


def render_league_overview(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    verify_ssl: bool = False,
) -> None:
    """
    Render the league overview page.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        verify_ssl: Whether to verify SSL certificates
    """
    # Fetch standings data from API
    response_data = None
    try:
        headers = {"Authorization": f"Bearer {auth_token}"}

        with httpx.Client(base_url=api_base_url, headers=headers, verify=verify_ssl, timeout=30.0) as client:
            response = client.get(f"/api/league/{league_key}/standings")
            if response.status_code == 200:
                response_data = response.json()
            elif response.status_code == 401:
                st.error("Session expired. Please log in again.")
                return
            else:
                st.error(f"Failed to fetch league data: {response.status_code}")
                return
    except Exception as e:
        st.error(f"Error fetching league data: {e}")
        return

    # Extract data and cache info
    data = response_data.get("data", {})
    cache_info = response_data.get("cache", {})
    league_info = data.get("league", {})
    teams = data.get("teams", [])

    # League header
    st.title(f"{league_info.get('name', 'League Overview')}")

    # Cache indicator
    render_cache_indicator(cache_info)

    # League stats row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Season", league_info.get("season", "N/A"))

    with col2:
        st.metric("Current Week", league_info.get("current_week", "N/A"))

    with col3:
        st.metric("Teams", league_info.get("num_teams", "N/A"))

    with col4:
        scoring = league_info.get("scoring_type", "N/A")
        scoring_display = scoring.replace("_", " ").title() if scoring else "N/A"
        st.metric("Scoring", scoring_display)

    st.divider()

    # Standings table
    st.subheader("Current Standings")

    if teams:
        # Create a visual display for top teams
        for team in teams:
            rank = team.get("rank", 0)
            # Medal for top 3
            if rank == 1:
                rank_display = "1st"
            elif rank == 2:
                rank_display = "2nd"
            elif rank == 3:
                rank_display = "3rd"
            else:
                rank_display = f"#{rank}"

            col1, col2, col3 = st.columns([1, 4, 2])

            with col1:
                st.markdown(f"### {rank_display}")

            with col2:
                st.markdown(f"**{team.get('team_name', 'Unknown')}**")
                wins = team.get("wins", 0)
                losses = team.get("losses", 0)
                ties = team.get("ties", 0)
                record = f"{wins}-{losses}"
                if ties > 0:
                    record += f"-{ties}"
                st.caption(record)

            with col3:
                win_pct = team.get("win_pct", 0)
                # Color based on win percentage
                if win_pct >= 60:
                    color = "green"
                elif win_pct >= 40:
                    color = "orange"
                else:
                    color = "red"
                st.markdown(f":{color}[{win_pct:.1f}%]")

        # Show detailed stats table
        st.divider()
        st.subheader("Season Stats by Team")
        st.caption(
            "All season longs totals for each of the statistical categories. "
            "Along with the record and win percentage for each team. "
            "The standings table is updated weekly. "
        )

        # Build dataframe with all stats
        rows = []
        for team in teams:
            wins = team.get("wins", 0)
            losses = team.get("losses", 0)
            ties = team.get("ties", 0)
            record = f"{wins}-{losses}" + (f"-{ties}" if ties > 0 else "")

            row = {
                "Rank": team.get("rank", 0),
                "Team": team.get("team_name", "Unknown"),
                "Record": record,
                "Win %": team.get("win_pct", 0),
            }
            # Add individual stats
            stats = team.get("stats", {})
            for stat_name in ["FG%", "FT%", "3PTM", "PTS", "REB", "AST", "STL", "BLK", "TO"]:
                row[stat_name] = stats.get(stat_name, "-")
            rows.append(row)

        df = pd.DataFrame(rows)

        # Format percentages
        df["Win %"] = df["Win %"].apply(lambda x: f"{x:.1f}%")
        if "FG%" in df.columns:
            df["FG%"] = df["FG%"].apply(lambda x: f"{x:.3f}" if isinstance(x, (int, float)) else x)
        if "FT%" in df.columns:
            df["FT%"] = df["FT%"].apply(lambda x: f"{x:.3f}" if isinstance(x, (int, float)) else x)

        st.dataframe(df, use_container_width=True, hide_index=True)

        # ROTO Table
        st.divider()
        st.subheader("ROTO Table")
        st.caption(
            "Rankings for each statistical category across the season. "
            "Rank 1 is best in each category. The Total column sums all rankings — "
            "lower total means better overall performance."
        )

        # Calculate rankings for each stat category
        num_teams = len(teams)
        roto_data = []

        for team in teams:
            team_name = team.get("team_name", "Unknown")
            stats = team.get("stats", {})
            roto_data.append({
                "team_name": team_name,
                **{stat: stats.get(stat, 0) for stat in STAT_CATEGORIES}
            })

        roto_df = pd.DataFrame(roto_data)

        # Calculate rankings for each stat (1 = best)
        ranking_rows = []
        for idx, row in roto_df.iterrows():
            ranking_row = {"Team": row["team_name"]}
            total_rank = 0

            for stat in STAT_CATEGORIES:
                stat_values = roto_df[stat].tolist()
                current_val = row[stat]

                # Sort values and find rank
                if stat in LOWER_IS_BETTER:
                    # Lower is better (e.g., TO) - ascending order
                    sorted_vals = sorted(enumerate(stat_values), key=lambda x: x[1])
                else:
                    # Higher is better - descending order
                    sorted_vals = sorted(enumerate(stat_values), key=lambda x: x[1], reverse=True)

                # Find rank (1-based)
                rank = 1
                for i, (orig_idx, val) in enumerate(sorted_vals):
                    if orig_idx == idx:
                        rank = i + 1
                        break

                ranking_row[stat] = rank
                total_rank += rank

            ranking_row["Total"] = total_rank
            ranking_rows.append(ranking_row)

        # Sort by Total (ascending - lower is better)
        ranking_df = pd.DataFrame(ranking_rows)
        ranking_df = ranking_df.sort_values("Total").reset_index(drop=True)

        # Style: highlight rank 1 in green, last rank in red
        def highlight_roto_ranks(val, col):
            if col == "Team" or col == "Total":
                return ""
            if val == 1:
                return f"background-color: {COLOR_WIN}; font-weight: bold"
            elif val == num_teams:
                return f"background-color: {COLOR_LOSE}"
            return ""

        def highlight_total(val):
            min_total = ranking_df["Total"].min()
            max_total = ranking_df["Total"].max()
            if val == min_total:
                return f"background-color: {COLOR_WIN}; font-weight: bold"
            elif val == max_total:
                return f"background-color: {COLOR_LOSE}"
            return ""

        # Apply styling
        styled_roto = ranking_df.style.applymap(
            lambda val: highlight_roto_ranks(val, "stat"),
            subset=STAT_CATEGORIES
        ).applymap(highlight_total, subset=["Total"])

        st.dataframe(styled_roto, use_container_width=True, hide_index=True)

    else:
        st.info("No standings data available.")
