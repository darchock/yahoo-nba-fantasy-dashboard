"""
Periodical analysis page with aggregated totals and rankings.

Displays stats aggregated across a user-defined week range.
"""

import streamlit as st
import httpx
import pandas as pd


# Stat categories in display order
STAT_CATEGORIES = ["FG%", "FT%", "3PTM", "PTS", "REB", "AST", "STL", "BLK", "TO"]


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

        with httpx.Client(base_url=api_base_url, headers=headers, verify=verify_ssl, timeout=60.0) as client:
            response = client.get(endpoint, params=params)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                st.error("Session expired. Please log in again.")
                return None
            elif response.status_code == 400:
                error_detail = response.json().get("detail", "Invalid request")
                st.error(f"Validation error: {error_detail}")
                return None
            else:
                st.error(f"Failed to fetch data: {response.status_code}")
                return None
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None


def render_periodical_totals_tab(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    start_week: int,
    end_week: int,
    verify_ssl: bool = False,
) -> None:
    """
    Render the periodical totals table.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        start_week: First week of period
        end_week: Last week of period
        verify_ssl: Whether to verify SSL certificates
    """
    with st.spinner(f"Loading totals for weeks {start_week}-{end_week}..."):
        result = fetch_api_data(
            api_base_url=api_base_url,
            auth_token=auth_token,
            endpoint=f"/api/league/{league_key}/periodical-totals",
            params={"start_week": start_week, "end_week": end_week},
            verify_ssl=verify_ssl,
        )

    if result is None:
        return

    data = result.get("data", {})
    teams = data.get("teams", [])
    stat_categories = data.get("stat_categories", STAT_CATEGORIES)

    if not teams:
        st.info("No team data available for this period.")
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


def render_periodical_rankings_tab(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    start_week: int,
    end_week: int,
    verify_ssl: bool = False,
) -> None:
    """
    Render the periodical rankings table.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        start_week: First week of period
        end_week: Last week of period
        verify_ssl: Whether to verify SSL certificates
    """
    with st.spinner(f"Loading rankings for weeks {start_week}-{end_week}..."):
        result = fetch_api_data(
            api_base_url=api_base_url,
            auth_token=auth_token,
            endpoint=f"/api/league/{league_key}/periodical-rankings",
            params={"start_week": start_week, "end_week": end_week},
            verify_ssl=verify_ssl,
        )

    if result is None:
        return

    data = result.get("data", {})
    teams = data.get("teams", [])
    stat_categories = data.get("stat_categories", STAT_CATEGORIES)
    num_teams = data.get("num_teams", len(teams))

    if not teams:
        st.info("No team data available for this period.")
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

    # Style: highlight rank 1 in green, last rank in red
    def highlight_ranks(val):
        if val == 1:
            return "background-color: #d4edda; font-weight: bold"
        elif val == num_teams:
            return "background-color: #f8d7da"
        return ""

    styled_df = df.style.applymap(highlight_ranks, subset=stat_categories)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)


def render_periodical_page(
    api_base_url: str,
    auth_token: str,
    league_key: str,
    verify_ssl: bool = False,
) -> None:
    """
    Render the periodical analysis page with week range picker and tabs.

    Args:
        api_base_url: Base URL for the API
        auth_token: JWT authentication token
        league_key: Yahoo league key
        verify_ssl: Whether to verify SSL certificates
    """
    st.title("Periodical Analysis")

    st.markdown("Analyze aggregated stats across a range of weeks.")

    # Week range picker
    col1, col2, col3 = st.columns([1, 1, 3])

    week_options = list(range(1, 20))  # Weeks 1-19 (regular season)

    with col1:
        start_week = st.selectbox(
            "Start Week",
            options=week_options,
            index=None,
            placeholder="From...",
            key="period_start_week",
        )

    with col2:
        end_week = st.selectbox(
            "End Week",
            options=week_options,
            index=None,
            placeholder="To...",
            key="period_end_week",
        )

    # Client-side validation
    validation_error = None

    if start_week is None or end_week is None:
        st.info("Select a start and end week to view aggregated data.")
        return

    if start_week > end_week:
        validation_error = "Start week must be less than or equal to end week."

    if validation_error:
        st.error(validation_error)
        return

    # Show period summary
    num_weeks = end_week - start_week + 1
    with col3:
        st.caption(f"Analyzing {num_weeks} week{'s' if num_weeks > 1 else ''} (Week {start_week} to {end_week})")

    st.divider()

    # Content tabs
    tab1, tab2 = st.tabs(["Totals", "Rankings"])

    with tab1:
        render_periodical_totals_tab(
            api_base_url=api_base_url,
            auth_token=auth_token,
            league_key=league_key,
            start_week=start_week,
            end_week=end_week,
            verify_ssl=verify_ssl,
        )

    with tab2:
        render_periodical_rankings_tab(
            api_base_url=api_base_url,
            auth_token=auth_token,
            league_key=league_key,
            start_week=start_week,
            end_week=end_week,
            verify_ssl=verify_ssl,
        )
