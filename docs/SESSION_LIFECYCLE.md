# Session & Token Lifecycle

Overview of authentication lifespans in the Yahoo Fantasy Dashboard.

## Token Lifespans

| Component | Lifespan | Purpose |
|---|---|---|
| **Session** (cookie) | 30 days | Keeps user logged in across tabs/devices |
| **JWT token** | 7 days | Short-lived API authentication, refreshed from session |
| **Yahoo OAuth access token** | 1 hour | Auto-refreshed transparently via refresh token |
| Auth code | 60 seconds | One-time use during OAuth login flow |
| Device link code | 3 minutes | QR code pairing for mobile devices |

## Configuration

- `SESSION_EXPIRE_DAYS` env var (default: `30`) — controls session cookie lifespan
- `JWT_EXPIRE_HOURS` constant in `backend/routes/auth.py` (default: `168` / 7 days)
- Yahoo OAuth token expiry is set by Yahoo (1 hour), not configurable

## Flow When Returning to the App

1. Browser sends session cookie
2. `/session/validate` confirms session is still valid, issues a fresh JWT
3. JWT is used for API calls to the FastAPI backend
4. If the Yahoo OAuth token is expired, `get_valid_access_token()` refreshes it automatically
5. If a request gets a 401 from Yahoo mid-flight (race condition), `make_request()` retries once after refreshing

## Re-login Required When

- Session expires (30+ days of inactivity)
- User explicitly logs out (session invalidated)
- Yahoo revokes the refresh token (rare)
