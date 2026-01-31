"""
Main Streamlit dashboard application.

Run with: streamlit run dashboard/main.py
"""

import os
import io
import base64

import streamlit as st
import httpx
import qrcode
from typing import Optional
from dotenv import load_dotenv
from streamlit_cookies_manager import EncryptedCookieManager

from app.logging_config import get_logger
from dashboard.views.home import render_league_overview
from dashboard.views.weekly import render_weekly_page
from dashboard.views.periodical import render_periodical_page
from dashboard.views.transactions import render_transactions_page

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

# Configuration from environment
API_BASE_URL = os.getenv("API_BASE_URL", "https://localhost:8080")
# Disable SSL verification for local dev with self-signed certs (set to "true" in production)
VERIFY_SSL = os.getenv("VERIFY_SSL", "false").lower() == "true"

# Log startup configuration
logger.info(f"Dashboard starting - API_BASE_URL={API_BASE_URL}, VERIFY_SSL={VERIFY_SSL}")

# Page config
st.set_page_config(
    page_title="Yahoo Fantasy Basketball Dashboard",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Cookie encryption key (should match APP_SECRET_KEY or be derived from it)
COOKIE_PASSWORD = os.getenv("APP_SECRET_KEY", "dev-secret-change-in-production")

# Session cookie name
SESSION_COOKIE_NAME = "fantasy_session"


def get_cookie_manager() -> EncryptedCookieManager:
    """Get the encrypted cookie manager instance."""
    return EncryptedCookieManager(
        prefix="fantasy_dashboard_",
        password=COOKIE_PASSWORD,
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
    if "is_first_login" not in st.session_state:
        st.session_state.is_first_login = False
    if "show_qr_dialog" not in st.session_state:
        st.session_state.show_qr_dialog = False
    if "qr_code_data" not in st.session_state:
        st.session_state.qr_code_data = None


def generate_qr_code_image(url: str) -> str:
    """
    Generate a QR code image for the given URL.

    Returns:
        Base64 encoded PNG image data
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    return img_base64


def generate_device_link_code() -> Optional[dict]:
    """
    Generate a device link code from the API.

    Returns:
        Dict with code, link_url, expires_in_seconds, or None if failed
    """
    if not st.session_state.auth_token:
        return None

    try:
        with httpx.Client(base_url=API_BASE_URL, verify=VERIFY_SSL, timeout=30.0) as client:
            response = client.post(
                "/auth/yahoo/device/generate-code",
                headers={"Authorization": f"Bearer {st.session_state.auth_token}"},
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to generate device link code: {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"Failed to generate device link code: {e}")
        return None


def handle_device_link_callback(cookies: EncryptedCookieManager) -> bool:
    """
    Handle device link callback from URL parameters.

    When a user scans a QR code, they're directed to the dashboard with a link_code parameter.
    This function exchanges that code for a session.

    Returns:
        True if device was linked successfully, False otherwise
    """
    params = st.query_params

    if "link_code" not in params:
        return False

    link_code = params["link_code"]
    # Clear the URL parameters immediately
    st.query_params.clear()

    logger.info("Processing device link code")
    try:
        with httpx.Client(base_url=API_BASE_URL, verify=VERIFY_SSL, timeout=30.0) as client:
            response = client.post(
                "/auth/yahoo/device/link",
                params={"code": link_code},
            )

            if response.status_code == 200:
                data = response.json()
                st.session_state.auth_token = data["access_token"]
                st.session_state.user_id = data["user"]["id"]

                # Store session ID in cookie for persistence
                session_id = data.get("session_id")
                if session_id:
                    cookies[SESSION_COOKIE_NAME] = session_id
                    cookies.save()

                logger.info("Device linked successfully via QR code")
                st.success("Device linked successfully! You are now logged in.")
                st.rerun()
                return True
            else:
                error_detail = response.json().get("detail", "Invalid or expired code")
                logger.warning(f"Device link failed: {error_detail}")
                st.error(f"Failed to link device: {error_detail}")
                return False
    except Exception as e:
        logger.error(f"Failed to link device: {e}")
        st.error(f"Failed to link device: {e}")
        return False


def handle_oauth_callback(cookies: EncryptedCookieManager) -> None:
    """Handle OAuth callback from URL parameters."""
    params = st.query_params

    # Check for authorization code in URL (set by FastAPI callback)
    if "code" in params:
        code = params["code"]
        session_id = params.get("session")  # Also get session ID from URL

        # Check if this is first login (no existing session cookie)
        existing_session = cookies.get(SESSION_COOKIE_NAME)
        is_first_login = not existing_session

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

                    # Store session ID in cookie for persistence across refreshes
                    if session_id:
                        cookies[SESSION_COOKIE_NAME] = session_id
                        cookies.save()

                    # Mark as first login to show QR code popup
                    if is_first_login:
                        st.session_state.is_first_login = True
                        st.session_state.show_qr_dialog = True
                        logger.info("Session cookie saved for persistent auth")

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


def restore_session_from_cookie(cookies: EncryptedCookieManager) -> bool:
    """
    Try to restore session from browser cookie.

    Validates the session with the backend and restores the auth token.

    Returns:
        True if session was restored, False otherwise
    """
    if st.session_state.auth_token:
        # Already have a token, no need to restore
        return True

    session_id = cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return False

    logger.debug("Found session cookie, validating with backend")
    try:
        with httpx.Client(base_url=API_BASE_URL, verify=VERIFY_SSL, timeout=30.0) as client:
            response = client.post(
                "/auth/yahoo/session/validate",
                params={"session_id": session_id},
            )

            if response.status_code == 200:
                data = response.json()
                token = data["access_token"]
                st.session_state.auth_token = token
                st.session_state.user_id = data["user"]["id"]
                logger.info(f"Session restored from cookie, token set: {token[:20]}...")
                # Verify it was actually set
                verify_token = st.session_state.get("auth_token")
                logger.debug(f"Verification - session_state.auth_token is set: {verify_token is not None}")
                return True
            else:
                # Session invalid/expired - clear the cookie
                logger.debug("Session cookie invalid or expired, clearing")
                del cookies[SESSION_COOKIE_NAME]
                cookies.save()
                return False
    except Exception as e:
        logger.warning(f"Failed to validate session: {e}")
        return False


def clear_session(cookies: EncryptedCookieManager) -> None:
    """
    Clear the session both locally and on the server.

    Called when user logs out.
    """
    # Invalidate server session
    session_id = cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        try:
            with httpx.Client(base_url=API_BASE_URL, verify=VERIFY_SSL, timeout=10.0) as client:
                client.post(
                    "/auth/yahoo/session/invalidate",
                    params={"session_id": session_id},
                )
        except Exception as e:
            logger.warning(f"Failed to invalidate server session: {e}")

        # Clear cookie
        del cookies[SESSION_COOKIE_NAME]
        cookies.save()

    # Clear local session state
    st.session_state.auth_token = None
    st.session_state.user_id = None
    st.session_state.leagues = []
    st.session_state.selected_league = None
    logger.info("User logged out, session cleared")


def get_api_client() -> httpx.Client:
    """Get configured HTTP client for API calls."""
    headers = {}
    token = st.session_state.get("auth_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
        logger.debug(f"API client using auth token: {token[:20]}...")
    else:
        logger.warning("API client created WITHOUT auth token - session_state.auth_token is None")

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
            elif response.status_code == 401:
                logger.debug("Auth check returned 401 - token expired or invalid")
            else:
                logger.warning(f"Auth check returned unexpected status: {response.status_code}")
    except httpx.TimeoutException:
        logger.warning("Auth check timed out")
    except httpx.RequestError as e:
        logger.warning(f"Auth check network error: {e}")
    except Exception as e:
        logger.warning(f"Auth check failed unexpectedly: {e}")

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


def check_backend_health() -> tuple[bool, str]:
    """
    Check if the FastAPI backend is reachable.

    Returns:
        Tuple of (is_healthy, error_message)
    """
    try:
        with httpx.Client(verify=VERIFY_SSL, timeout=5.0) as client:
            response = client.get(f"{API_BASE_URL}/health")
            if response.status_code == 200:
                return True, ""
            return False, f"Backend returned status {response.status_code}"
    except httpx.ConnectError as e:
        return False, f"Cannot connect to backend at {API_BASE_URL}. Is the FastAPI server running?"
    except httpx.ConnectTimeout:
        return False, f"Connection to backend at {API_BASE_URL} timed out"
    except Exception as e:
        return False, f"Backend health check failed: {e}"


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
            # Check backend health before redirecting
            logger.info(f"User clicked login - checking backend health at {API_BASE_URL}")
            is_healthy, error_msg = check_backend_health()

            if not is_healthy:
                logger.error(f"Backend health check failed: {error_msg}")
                st.error(f"**Cannot connect to backend server**\n\n{error_msg}\n\nMake sure the FastAPI server is running:\n```\npython -m uvicorn backend.main:app --host localhost --port 8080 --ssl-keyfile key.pem --ssl-certfile cert.pem\n```")
            else:
                logger.info(f"Backend healthy, redirecting to {login_url}")
                # Use JavaScript to redirect in the same tab
                st.markdown(
                    f'<meta http-equiv="refresh" content="0;url={login_url}">',
                    unsafe_allow_html=True,
                )

        st.caption("You'll be redirected to Yahoo to authorize access to your fantasy data.")


def render_sidebar(cookies: EncryptedCookieManager) -> None:
    """Render the sidebar with league selector and navigation."""
    with st.sidebar:
        st.title("Fantasy Dashboard")

        st.divider()

        # League selector
        st.subheader("Select League")

        # Load leagues if not cached
        if not st.session_state.leagues:
            # First try without sync (fast, from database)
            st.session_state.leagues = fetch_leagues(sync=False)

            # If no leagues found, sync from Yahoo (first login)
            if not st.session_state.leagues:
                with st.spinner("Fetching leagues from Yahoo..."):
                    st.session_state.leagues = fetch_leagues(sync=True)

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
            st.warning("No NBA fantasy leagues found for your Yahoo account.")

        st.divider()

        # Page navigation
        st.subheader("Navigation")
        page_options = ["Home", "Weekly", "Periodical", "Transactions"]
        current_index = page_options.index(st.session_state.current_page) if st.session_state.current_page in page_options else 0
        page = st.radio(
            "Page",
            options=page_options,
            index=current_index,
            label_visibility="collapsed",
        )
        st.session_state.current_page = page

        st.divider()

        # Link Device (QR Code)
        st.subheader("Link Device")
        if st.button("Generate QR Code", use_container_width=True, help="Scan with another device to login"):
            qr_data = generate_device_link_code()
            if qr_data:
                show_qr_code_dialog(qr_data, is_first_login=False)
            else:
                st.error("Failed to generate QR code. Please try again.")

        st.divider()

        # Logout
        if st.button("Logout", use_container_width=True):
            clear_session(cookies)
            st.rerun()


@st.dialog("Link Another Device")
def show_qr_code_dialog(qr_data: dict, is_first_login: bool = False) -> None:
    """
    Display QR code in a modal dialog.

    Uses Streamlit's @st.dialog decorator for a proper popup with X button.
    """
    if is_first_login:
        st.info(
            "**Welcome!** Scan this QR code with your phone to login "
            "on mobile without needing to go through Yahoo login again."
        )
    else:
        st.markdown("Scan this QR code with another device to login instantly.")

    # Generate and display QR code
    qr_image_base64 = generate_qr_code_image(qr_data["link_url"])
    st.markdown(
        f'<div style="display: flex; justify-content: center; padding: 20px 0;">'
        f'<img src="data:image/png;base64,{qr_image_base64}" width="250" />'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Show expiration info
    expires_in = qr_data.get("expires_in_seconds", 180)
    st.caption(f"Code expires in {expires_in // 60} minutes. Close this dialog when done scanning.")


def render_dashboard(cookies: EncryptedCookieManager) -> None:
    """Render the main dashboard content."""
    # Show QR code dialog for first login
    if st.session_state.show_qr_dialog and st.session_state.is_first_login:
        qr_data = st.session_state.qr_code_data
        if not qr_data:
            qr_data = generate_device_link_code()
            st.session_state.qr_code_data = qr_data
        if qr_data:
            show_qr_code_dialog(qr_data, is_first_login=True)
        # Reset the flag after showing
        st.session_state.show_qr_dialog = False
        st.session_state.is_first_login = False

    render_sidebar(cookies)

    if not st.session_state.selected_league:
        st.title("Yahoo Fantasy Basketball Dashboard")
        st.info("Please select a league from the sidebar to view data.")

        # Show welcome message
        st.markdown("""
        ### Welcome!

        Select a league from the sidebar to see:
        - **Home** - League standings and season stats
        - **Weekly** - Scoreboard and matchup analysis
        - **Periodical** - Aggregated stats across multiple weeks

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
    elif st.session_state.current_page == "Periodical":
        render_periodical_page(
            api_base_url=API_BASE_URL,
            auth_token=st.session_state.auth_token,
            league_key=league_key,
            verify_ssl=VERIFY_SSL,
        )
    elif st.session_state.current_page == "Transactions":
        render_transactions_page(
            api_base_url=API_BASE_URL,
            auth_token=st.session_state.auth_token,
            league_key=league_key,
            verify_ssl=VERIFY_SSL,
        )


def main() -> None:
    """Main application entry point."""
    logger.debug("Dashboard page render started")
    init_session_state()

    # Initialize cookie manager
    cookies = get_cookie_manager()

    # Wait for cookies to be ready (required by streamlit-cookies-manager)
    if not cookies.ready():
        st.spinner("Loading...")
        st.stop()

    # Handle device link callback (QR code login) - check this first
    if "link_code" in st.query_params:
        handle_device_link_callback(cookies)
        return  # Will rerun after successful link

    # Handle OAuth callback (if coming back from login)
    handle_oauth_callback(cookies)

    # Try to restore session from cookie if not already authenticated
    if not st.session_state.auth_token:
        restore_session_from_cookie(cookies)

    # Check authentication
    if st.session_state.auth_token:
        render_dashboard(cookies)
    else:
        render_login_page()


if __name__ == "__main__":
    main()
