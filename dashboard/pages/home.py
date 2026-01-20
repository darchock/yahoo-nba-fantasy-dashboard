"""
Home page with league overview.
"""

import streamlit as st
from typing import Optional
import httpx


def parse_standings(standings_data: dict) -> list[dict]:
    """Parse standings data from Yahoo API response."""
    table_data = []

    try:
        standings_list = standings_data.get("fantasy_content", {}).get("league", [])

        if len(standings_list) > 1:
            standings_info = standings_list[1].get("standings", [])
            teams = standings_info[0].get("teams", {}) if standings_info else {}

            team_count = teams.get("count", 0)

            for i in range(team_count):
                team_info = teams.get(str(i), {}).get("team", [])
                if not team_info:
                    continue

                # Extract team details
                team_details = team_info[0] if team_info else []
                team_standings = team_info[1].get("team_standings", {}) if len(team_info) > 1 else {}

                # Get team name
                team_name = ""
                team_logo = ""
                for item in team_details:
                    if isinstance(item, dict):
                        if "name" in item:
                            team_name = item["name"]
                        if "team_logos" in item:
                            logos = item["team_logos"]
                            if logos and len(logos) > 0:
                                team_logo = logos[0].get("team_logo", {}).get("url", "")

                rank = team_standings.get("rank", "")
                record = team_standings.get("outcome_totals", {})
                wins = int(record.get("wins", 0))
                losses = int(record.get("losses", 0))
                ties = int(record.get("ties", 0))
                total_games = wins + losses + ties

                table_data.append({
                    "rank": int(rank) if rank else 0,
                    "team_name": team_name,
                    "team_logo": team_logo,
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "win_pct": wins / max(total_games, 1) * 100,
                })

        # Sort by rank
        table_data.sort(key=lambda x: x["rank"])

    except Exception as e:
        st.error(f"Error parsing standings: {e}")

    return table_data


def parse_league_info(standings_data: dict) -> dict:
    """Extract league metadata from standings response."""
    try:
        league_list = standings_data.get("fantasy_content", {}).get("league", [])
        if league_list:
            league_info = league_list[0]
            return {
                "name": league_info.get("name", "Unknown League"),
                "num_teams": league_info.get("num_teams", 0),
                "current_week": league_info.get("current_week", 1),
                "start_week": league_info.get("start_week", 1),
                "end_week": league_info.get("end_week", 1),
                "season": league_info.get("season", ""),
                "scoring_type": league_info.get("scoring_type", ""),
            }
    except Exception:
        pass

    return {}


def render_league_overview(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    verify_ssl: bool = False,
) -> None:
    """Render the league overview page."""

    # Fetch standings data (contains league info too)
    standings_data = None
    try:
        headers = {"Authorization": f"Bearer {auth_token}"}
        with httpx.Client(base_url=api_base_url, headers=headers, verify=verify_ssl, timeout=30.0) as client:
            response = client.get(f"/api/league/{league_key}/standings")
            if response.status_code == 200:
                standings_data = response.json()
            elif response.status_code == 401:
                st.error("Session expired. Please log in again.")
                return
            else:
                st.error(f"Failed to fetch league data: {response.status_code}")
                return
    except Exception as e:
        st.error(f"Error fetching league data: {e}")
        return

    # Parse league info
    league_info = parse_league_info(standings_data)

    # League header
    st.title(f"🏀 {league_info.get('name', 'League Overview')}")

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
    st.subheader("📊 Current Standings")

    standings = parse_standings(standings_data)

    if standings:
        # Create a nice display
        for team in standings:
            rank = team["rank"]
            # Medal for top 3
            if rank == 1:
                rank_display = "🥇"
            elif rank == 2:
                rank_display = "🥈"
            elif rank == 3:
                rank_display = "🥉"
            else:
                rank_display = f"#{rank}"

            col1, col2, col3 = st.columns([1, 4, 2])

            with col1:
                st.markdown(f"### {rank_display}")

            with col2:
                st.markdown(f"**{team['team_name']}**")
                record = f"{team['wins']}-{team['losses']}"
                if team['ties'] > 0:
                    record += f"-{team['ties']}"
                st.caption(record)

            with col3:
                win_pct = team['win_pct']
                # Color based on win percentage
                if win_pct >= 60:
                    color = "green"
                elif win_pct >= 40:
                    color = "orange"
                else:
                    color = "red"
                st.markdown(f":{color}[{win_pct:.1f}%]")

        # Also show as dataframe for sortability
        with st.expander("View as Table"):
            import pandas as pd
            df = pd.DataFrame(standings)
            df = df.rename(columns={
                "rank": "Rank",
                "team_name": "Team",
                "wins": "W",
                "losses": "L",
                "ties": "T",
                "win_pct": "Win %",
            })
            df = df[["Rank", "Team", "W", "L", "T", "Win %"]]
            df["Win %"] = df["Win %"].apply(lambda x: f"{x:.1f}%")
            st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No standings data available.")

    # Quick links to other sections
    st.divider()
    st.subheader("Quick Navigation")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("📈 **Scoreboard**\nView weekly matchup scores")
    with col2:
        st.info("⚔️ **Matchups**\nSee head-to-head matchups")
    with col3:
        st.info("📋 **Transactions**\nRecent adds, drops, trades")
