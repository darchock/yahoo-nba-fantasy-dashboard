"""
Main Streamlit dashboard application.

Run with: streamlit run dashboard/main.py
"""

import os

import streamlit as st
import httpx
from typing import Optional
from dotenv import load_dotenv

from app.logging_config import get_logger
from dashboard.views.home import render_league_overview
from dashboard.views.weekly import render_weekly_page

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

# Configuration from environment
API_BASE_URL = os.getenv("API_BASE_URL", "https://localhost:8080")
# Disable SSL verification for local dev with self-signed certs (set to "true" in production)
VERIFY_SSL = os.getenv("VERIFY_SSL", "false").lower() == "true"

# Page config
st.set_page_config(
    page_title="Yahoo Fantasy Basketball Dashboard",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state() -> None:
    """Initialize session state variables."""
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = None
    if "selected_league" not in st.session_state:
        st.session_state.selected_league = None
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Home"
    if "leagues" not in st.session_state:
        st.session_state.leagues = []


def handle_oauth_callback() -> None:
    """Handle OAuth callback from URL parameters."""
    params = st.query_params

    # Check for authorization code in URL (set by FastAPI callback)
    if "code" in params:
        code = params["code"]
        # Clear the URL parameters immediately
        st.query_params.clear()

        # Exchange the code for a JWT token
        logger.debug("Exchanging auth code for JWT token")
        try:
            with httpx.Client(base_url=API_BASE_URL, verify=VERIFY_SSL, timeout=30.0) as client:
                response = client.post(
                    "/auth/yahoo/exchange",
                    params={"code": code},
                )

                if response.status_code == 200:
                    token_data = response.json()
                    st.session_state.auth_token = token_data["access_token"]
                    logger.info("User authenticated successfully via OAuth")
                    st.rerun()
                else:
                    error_detail = response.json().get("detail", "Unknown error")
                    logger.warning(f"Authentication failed: {error_detail}")
                    st.error(f"Authentication failed: {error_detail}")
        except Exception as e:
            logger.error(f"Failed to complete authentication: {e}")
            st.error(f"Failed to complete authentication: {e}")

    # Check for error
    if "error" in params:
        st.error(f"Authentication failed: {params.get('error_description', params['error'])}")
        st.query_params.clear()


def get_api_client() -> httpx.Client:
    """Get configured HTTP client for API calls."""
    headers = {}
    if st.session_state.auth_token:
        headers["Authorization"] = f"Bearer {st.session_state.auth_token}"

    return httpx.Client(
        base_url=API_BASE_URL,
        headers=headers,
        verify=VERIFY_SSL,
        timeout=30.0,
    )


def check_auth_status() -> Optional[dict]:
    """Check if user is authenticated with the backend."""
    if not st.session_state.auth_token:
        return None

    try:
        with get_api_client() as client:
            response = client.get("/auth/yahoo/me")
            if response.status_code == 200:
                return response.json()
    except Exception:
        pass

    return None


def fetch_leagues(sync: bool = False) -> list:
    """Fetch user's leagues from API."""
    try:
        logger.debug(f"Fetching leagues (sync={sync})")
        with get_api_client() as client:
            response = client.get("/api/user/leagues", params={"sync": sync})
            if response.status_code == 200:
                leagues = response.json()
                logger.debug(f"Fetched {len(leagues)} leagues")
                return leagues
            elif response.status_code == 401:
                # Token expired or invalid
                logger.warning("Token expired or invalid, clearing session")
                st.session_state.auth_token = None
                st.session_state.user_id = None
                st.rerun()
    except Exception as e:
        logger.error(f"Failed to fetch leagues: {e}")
        st.error(f"Failed to fetch leagues: {e}")

    return []


def render_login_page() -> None:
    """Render the login page for unauthenticated users."""
    st.title("Yahoo Fantasy Basketball Dashboard")

    st.markdown("""
    Welcome to the Yahoo Fantasy Basketball Dashboard!

    This dashboard provides insights and visualizations for your Yahoo Fantasy Basketball leagues.

    **Features:**
    - View league standings and statistics
    - Analyze weekly matchups
    - Track trends over the season
    - Compare team performance
    """)

    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("Get Started")
        st.markdown("Connect your Yahoo account to access your leagues.")

        # Login button - redirects to FastAPI OAuth endpoint (same tab)
        login_url = f"{API_BASE_URL}/auth/yahoo/login"
        if st.button("Login with Yahoo", use_container_width=True, type="primary"):
            # Use JavaScript to redirect in the same tab
            st.markdown(
                f'<meta http-equiv="refresh" content="0;url={login_url}">',
                unsafe_allow_html=True,
            )

        st.caption("You'll be redirected to Yahoo to authorize access to your fantasy data.")


def render_sidebar() -> None:
    """Render the sidebar with league selector and navigation."""
    with st.sidebar:
        st.title("Fantasy Dashboard")

        st.divider()

        # League selector
        st.subheader("Select League")

        # Load leagues if not cached
        if not st.session_state.leagues:
            st.session_state.leagues = fetch_leagues()

        leagues = st.session_state.leagues

        if leagues:
            league_options = {
                league["league_name"]: league["league_key"]
                for league in leagues
            }

            selected_name = st.selectbox(
                "League",
                options=list(league_options.keys()),
                label_visibility="collapsed",
            )

            if selected_name:
                st.session_state.selected_league = league_options[selected_name]
        else:
            st.info("No leagues found. Click sync to fetch from Yahoo.")

        st.divider()

        # Page navigation
        st.subheader("Navigation")
        page = st.radio(
            "Page",
            options=["Home", "Weekly"],
            index=0 if st.session_state.current_page == "Home" else 1,
            label_visibility="collapsed",
        )
        st.session_state.current_page = page

        st.divider()

        # Logout
        if st.button("Logout", use_container_width=True):
            # Clear session state
            logger.info("User logging out from dashboard")
            st.session_state.auth_token = None
            st.session_state.user_id = None
            st.session_state.leagues = []
            st.session_state.selected_league = None
            st.rerun()


def render_dashboard() -> None:
    """Render the main dashboard content."""
    render_sidebar()

    if not st.session_state.selected_league:
        st.title("Yahoo Fantasy Basketball Dashboard")
        st.info("Please select a league from the sidebar to view data.")

        # Show welcome message
        st.markdown("""
        ### Welcome!

        Select a league from the sidebar to see:
        - **Home** - League standings and season stats
        - **Weekly** - Scoreboard and matchup analysis

        If you don't see any leagues, click the Sync button to fetch them from Yahoo.
        """)
        return

    # Get current league info
    league_key = st.session_state.selected_league

    # Render the selected page
    if st.session_state.current_page == "Home":
        render_league_overview(
            api_base_url=API_BASE_URL,
            auth_token=st.session_state.auth_token,
            league_key=league_key,
            verify_ssl=VERIFY_SSL,
        )
    elif st.session_state.current_page == "Weekly":
        render_weekly_page(
            api_base_url=API_BASE_URL,
            auth_token=st.session_state.auth_token,
            league_key=league_key,
            verify_ssl=VERIFY_SSL,
        )


def main() -> None:
    """Main application entry point."""
    logger.debug("Dashboard page render started")
    init_session_state()
    handle_oauth_callback()

    # Check authentication
    if st.session_state.auth_token:
        render_dashboard()
    else:
        render_login_page()


if __name__ == "__main__":
    main()
