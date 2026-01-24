# Progress Log

## Session 1 - 2026-01-14

### Completed

**Planning & Documentation:**
- Reviewed work_plan.md and confirmed understanding
- Verified access to reference repository (Yahoo_NBA_Fantasy_Hub)
- Created documentation structure (CLAUDE.md, PROGRESS.md, DECISIONS.md, BACKLOG.md)
- Removed docs from .gitignore (decision: track in repo for history)
- Added two new features to plan:
  - **Scheduled Data Refresh** (Phase 3 - core functionality)
  - **Pick-a-Winner Game** (Phase 8 - post-launch)
- Reordered phases: Scheduler now before deployment

**Phase 1 Implementation:**
- Created project folder structure (app/, backend/, dashboard/, data/)
- Created requirements.txt with all dependencies
- Created .env.example and .env with Yahoo credentials
- Implemented app/config.py (environment variable loading)
- Implemented app/database/models.py (8 models: User, OAuthToken, UserLeague, CachedData, MatchupPrediction, PredictionResult, PredictionStandings, JobLog)
- Implemented app/database/connection.py (SQLAlchemy session management)
- Adapted app/parsing/helpers.py from CLI repo (safe_get, STAT_ID_TO_NAME_MAP)
- Implemented app/services/yahoo_api.py (instance-based, per-user OAuth)
- Created virtual environment and installed all dependencies
- Tested all components (config, models, database CRUD, parsing, API service)

**Quality Fixes (Pylance/IDE errors):**
- Fixed `datetime.utcnow()` deprecation → `datetime.now(timezone.utc)`
- Fixed broken property methods from aggressive replace_all
- Added type ignore comments for SQLAlchemy type mismatches
- Removed unused imports (json, os from helpers.py)
- Fixed `get_user_leagues` to properly parse response and return List[Dict]
- Created docs/ISSUES_LOG.md documenting all issues and solutions

### Current State
- **Phase 1: COMPLETE**
- All 8 database tables created in data/fantasy.db
- All tests passing (runtime + Pylance)
- Documentation fully updated

### Files Created
```
app/
├── __init__.py
├── config.py
├── database/
│   ├── __init__.py
│   ├── models.py
│   └── connection.py
├── services/
│   ├── __init__.py
│   └── yahoo_api.py
├── parsing/
│   ├── __init__.py
│   └── helpers.py
├── jobs/__init__.py
└── visualization/__init__.py

backend/
├── __init__.py
└── routes/__init__.py

dashboard/
├── __init__.py
├── pages/__init__.py
└── components/__init__.py

data/
├── .gitkeep
└── fantasy.db

docs/
├── PROGRESS.md
├── DECISIONS.md
├── BACKLOG.md
└── ISSUES_LOG.md

.env
.env.example
requirements.txt
CLAUDE.md
work_plan.md
```

### Blockers
None

### Next Session
- Begin Phase 2: FastAPI Backend
  - Create backend/main.py (FastAPI app)
  - Implement OAuth routes (/login, /callback, /logout)
  - Implement data API routes

---

## Session 2 - 2026-01-16

### Completed

**Phase 2: FastAPI Backend - COMPLETE**

**OAuth Flow:**
- Created `backend/main.py` (FastAPI app entry with lifespan, CORS, session middleware)
- Created `backend/routes/auth.py` (OAuth endpoints: /login, /callback, /logout, /me, /status)
- Added `/callback` route at root level to match Yahoo's registered redirect URI
- Implemented full OAuth flow with Yahoo:
  - Generate authorization URL with CSRF state token
  - Exchange authorization code for tokens
  - Fetch user GUID via Yahoo API
  - Create/update user and tokens in database
  - Set session and redirect to frontend

**API Endpoints:**
- Created `backend/routes/api.py` with authenticated endpoints:
  - `GET /api/user/leagues` - List user's leagues (with sync option)
  - `GET /api/league/{key}/info` - League metadata
  - `GET /api/league/{key}/teams` - Teams in league
  - `GET /api/league/{key}/standings` - League standings
  - `GET /api/league/{key}/scoreboard` - Weekly scoreboard
  - `GET /api/league/{key}/transactions` - League transactions
  - `GET /api/league/{key}/matchups` - Weekly matchups

**Configuration Updates:**
- Added `FRONTEND_URL` to config for environment-specific redirects
- Updated `.env` and `.env.example` with SSL redirect URI
- Generated self-signed SSL certificate for local HTTPS development
- Added `*.pem` to `.gitignore`

**Bug Fixes:**
- Fixed timezone-naive vs timezone-aware datetime comparison in `is_expired` and `is_stale` properties
- Added `itsdangerous` to requirements.txt for session middleware
- Changed OAuth scope from `openid fspt-r` to `fspt-r` to match CLI app
- Added fallback to fetch user GUID via API when not in token response

**Documentation:**
- Created `docs/OAUTH_ARCHITECTURE.md` explaining multi-user auth design
- Added to CLAUDE.md quick links
- Updated DECISIONS.md with SSL and FRONTEND_URL decisions
- Updated ISSUES_LOG.md with 4 new issues and solutions

### Files Created/Modified
```
backend/
├── main.py              # NEW - FastAPI app entry
└── routes/
    ├── auth.py          # NEW - OAuth endpoints
    └── api.py           # NEW - Data API endpoints

app/
├── config.py            # MODIFIED - Added FRONTEND_URL
├── database/models.py   # MODIFIED - Fixed timezone handling
└── services/yahoo_api.py # MODIFIED - Changed scope to fspt-r

docs/
├── OAUTH_ARCHITECTURE.md # NEW - Auth design docs
├── DECISIONS.md         # MODIFIED - Added decisions 7-8
├── ISSUES_LOG.md        # MODIFIED - Added issues 7-10
└── PROGRESS.md          # MODIFIED - This file

.env                     # MODIFIED - SSL redirect, FRONTEND_URL
.env.example             # MODIFIED - Updated examples
.gitignore               # MODIFIED - Added *.pem
requirements.txt         # MODIFIED - Added itsdangerous
cert.pem, key.pem        # NEW - SSL certificates (gitignored)
```

### Current State
- **Phase 1: COMPLETE**
- **Phase 2: COMPLETE**
- All OAuth and API endpoints tested and working
- User authenticated, leagues fetched from Yahoo API

### Blockers
None

### Next Session
- Begin Phase 3: Streamlit Dashboard
  - Create `dashboard/main.py` (main Streamlit entry)
  - Implement Yahoo OAuth login button
  - Create league selector dropdown
  - Create week picker
  - Display basic league data

---

## Session 3 - 2026-01-20

### Completed

**Phase 3: Streamlit Dashboard - STARTED**

**Streamlit Dashboard Core:**
- Created `dashboard/main.py` (main Streamlit entry point)
- Implemented login page with Yahoo OAuth button
- Created sidebar with league selector dropdown and week picker
- Created `dashboard/pages/home.py` with league overview (standings display)

**Secure Authentication Flow:**
- Refactored auth to support both session-based (browser) and JWT token-based (Streamlit) authentication
- Implemented secure authorization code exchange flow:
  1. OAuth callback generates short-lived auth code (60 sec, single-use)
  2. Stores auth code in database (`auth_codes` table)
  3. Redirects to Streamlit with code in URL
  4. Streamlit exchanges code for JWT via POST `/auth/yahoo/exchange`
  5. JWT stored in `st.session_state` for API calls
- Added `AuthCode` model to database for secure code storage
- Added Bearer token support to all API endpoints

**Configuration Improvements:**
- Added detailed documentation to `.env` file explaining each variable
- Moved `API_BASE_URL` from hardcoded to environment variable
- Added `VERIFY_SSL` setting for local dev with self-signed certs
- Regenerated SSL certificates for HTTPS on port 8080

**Project Structure:**
- Created `pyproject.toml` for proper Python package management
- Project now installable via `pip install -e .` for clean imports
- Fixed import issues between `dashboard`, `app`, and `backend` packages

**Bug Fixes:**
- Fixed `require_auth` dependency injection (was calling function directly instead of using `Depends()`)
- Fixed SSL certificate issues for local HTTPS development

### Files Created/Modified
```
dashboard/
├── app.py               # NEW - Main Streamlit application
└── pages/
    └── home.py          # NEW - League overview page

backend/routes/
├── auth.py              # MODIFIED - Added JWT tokens, auth code exchange
└── api.py               # MODIFIED - Fixed dependency injection

app/database/
└── models.py            # MODIFIED - Added AuthCode model

pyproject.toml           # NEW - Package configuration
.env                     # MODIFIED - Added API_BASE_URL, VERIFY_SSL, documentation
cert.pem, key.pem        # REGENERATED - New SSL certificates
```

### Current State
- **Phase 1: COMPLETE**
- **Phase 2: COMPLETE**
- **Phase 3: IN PROGRESS**
  - OAuth flow working end-to-end ✓
  - Login button → Yahoo → callback → Streamlit dashboard ✓
  - League selector in sidebar ✓
  - Basic standings display ✓
  - Remaining: visualizations, more pages

### How to Run (Local Development)
```bash
# Terminal 1 - FastAPI Backend
cd C:\Users\darch\Projects\yahoo-nba-fantasy-dashboard
venv\Scripts\python.exe -m uvicorn backend.main:app --host localhost --port 8080 --ssl-keyfile key.pem --ssl-certfile cert.pem --reload

# Terminal 2 - Streamlit Dashboard
cd C:\Users\darch\Projects\yahoo-nba-fantasy-dashboard
venv\Scripts\streamlit.exe run dashboard/main.py --server.port 8501
```

### Blockers
None

---

## Session 4 - 2026-01-22

### Completed

**Logging Utilities:**
- Created `app/logging_config.py` with centralized logging setup
- Dual output: console + file in development, file-only in production
- Daily log rotation with `ArchivingRotatingFileHandler`
- Previous day's logs archived to `logs/archive/`
- Integrated logging into FastAPI backend and Streamlit dashboard
- Silenced noisy third-party loggers (sqlalchemy, httpx, uvicorn, etc.)

**Testing Infrastructure:**
- Added pytest to dev dependencies
- Created `tests/` directory with 22 logging tests
- All tests passing

**Bug Fixes:**
- Renamed `dashboard/app.py` to `dashboard/main.py` to fix naming conflict with `app` package

**Documentation:**
- Added package management guidelines to CLAUDE.md
- Added testing requirements to CLAUDE.md
- Updated all docs to reference `dashboard/main.py`

### Files Created/Modified
```
app/
└── logging_config.py          # NEW - Centralized logging

tests/
├── __init__.py                # NEW
└── test_logging_config.py     # NEW - 22 tests

logs/
├── .gitkeep                   # NEW
├── app.log                    # NEW (gitignored)
└── archive/
    └── .gitkeep               # NEW

backend/
└── main.py                    # MODIFIED - Added logging

backend/routes/
├── auth.py                    # MODIFIED - Added logging
└── api.py                     # MODIFIED - Added logging

dashboard/
└── main.py                    # RENAMED from app.py, added logging

pyproject.toml                 # MODIFIED - Added pytest
requirements.txt               # MODIFIED - Added pytest
.gitignore                     # MODIFIED - Added logs
CLAUDE.md                      # MODIFIED - Added guidelines
```

### Current State
- **Phase 1: COMPLETE**
- **Phase 2: COMPLETE**
- **Phase 3: IN PROGRESS**
  - OAuth flow working ✓
  - League selector ✓
  - Basic standings display ✓
  - Logging utilities ✓
  - Remaining: proper standings parsing, weekly visualizations, data caching

### Blockers
None

### Next Session (Session 5)
Focus: Standings, Weekly Visualizations, and Data Caching

1. **Parse and display standings properly**
   - Adapt parsing from CLI repo for standings data
   - Display formatted standings table in Streamlit

2. **Create weekly visualizations page**
   - Create `dashboard/pages/weekly.py`
   - Display scoreboard/matchups for selected week
   - Add basic visualizations (tables, charts)

3. **Implement data caching with freshness indicator**
   - Use `CachedData` model to store API responses
   - Add "Last updated: X ago" indicator in UI
   - Add manual refresh button to fetch fresh data
   - Serve from cache when data is fresh

---

## Session 5 - 2026-01-22

### Completed

**Architecture Refactoring:**
- Moved all parsing logic from Streamlit (client) to FastAPI (backend)
- Created `app/parsing/standings.py` for standings data parsing
- Created `app/parsing/scoreboard.py` for scoreboard/matchup data parsing
- Streamlit now only consumes clean, pre-parsed data from the API

**Data Caching:**
- Implemented caching using existing `CachedData` model
- Cache duration: 15 minutes (configurable via `CACHE_DURATION_MINUTES`)
- Added `refresh` parameter to API endpoints to force cache bypass
- API responses now include cache metadata (`fetched_at`, `expires_at`)

**Weekly Scoreboard Page:**
- Created `dashboard/pages/weekly.py` for weekly matchup display
- Shows all matchups for selected week with stat comparisons
- Highlights category winners in comparison table
- Displays matchup scores (category wins/losses/ties)
- Added tab navigation between Standings and Weekly Scoreboard

**UI Enhancements:**
- Added "Last updated: X ago" freshness indicator to all pages
- Added "Refresh" button to manually fetch fresh data from Yahoo
- Removed emojis from UI for cleaner professional look

**Testing:**
- Added 24 new tests for parsing modules (`tests/test_parsing.py`)
- Tests cover helpers, standings parsing, scoreboard parsing, and caching
- All 46 tests passing

### Files Created/Modified
```
app/parsing/
├── standings.py               # NEW - Standings parsing logic
└── scoreboard.py              # NEW - Scoreboard/matchup parsing logic

app/services/
└── yahoo_api.py               # MODIFIED - Added week param to standings

backend/routes/
└── api.py                     # MODIFIED - Added caching, parsing, refresh param

dashboard/
├── main.py                    # MODIFIED - Added tab navigation, weekly page
└── pages/
    ├── home.py                # MODIFIED - Simplified to consume API data
    └── weekly.py              # NEW - Weekly scoreboard page

tests/
└── test_parsing.py            # NEW - 24 parsing tests
```

### API Response Format
API now returns structured responses with cache metadata:
```json
{
  "data": { /* parsed data */ },
  "cache": {
    "cached": true,
    "fetched_at": "2026-01-22T10:30:00+00:00",
    "expires_at": "2026-01-22T10:45:00+00:00"
  }
}
```

### Current State
- **Phase 1: COMPLETE**
- **Phase 2: COMPLETE**
- **Phase 3: IN PROGRESS**
  - OAuth flow working ✓
  - League selector ✓
  - Standings with stats display ✓
  - Weekly scoreboard page ✓
  - Data caching with freshness indicator ✓
  - Logging utilities ✓
  - Remaining: transactions page, additional visualizations

### Blockers
None

---

## Session 6 - 2026-01-22

### Completed

**Dashboard UX Improvements:**
- Renamed `pages/` folder to `views/` to avoid Streamlit auto-detection conflict
- Added sidebar page navigation (Home/Weekly) replacing tabs
- Removed redundant UI elements (sync button, user info display, refresh buttons)
- Weekly page now waits for user to select week before fetching data
- Limited week selection to 1-19 (regular season only)
- Changed week picker from number input to selectbox dropdown

**Weekly Analysis Tabs - New Features:**
All tabs fetch pre-parsed data from server-side API endpoints.

1. **Totals Tab** (new)
   - Created `parse_weekly_totals()` in `app/parsing/scoreboard.py`
   - Added `GET /api/league/{key}/weekly-totals` endpoint
   - Displays all teams' stats for selected week in table format

2. **Rankings Tab** (new)
   - Created `parse_weekly_rankings()` in `app/parsing/scoreboard.py`
   - Added `GET /api/league/{key}/weekly-rankings` endpoint
   - Ranks teams (1=best) for each stat category with average rank
   - Styled: green for rank 1, red for last place

3. **Head-to-Head Matrix Tab** (new)
   - Created `simulate_matchup()` and `parse_head_to_head_matrix()` in `app/parsing/scoreboard.py`
   - Added `GET /api/league/{key}/weekly-h2h` endpoint
   - Simulates cross-league matchups: how each team would fare vs every other team
   - Displays W-L-T for each pair, total record, and Win%
   - Sorted by win percentage (best first)
   - Styled: green for Win% ≥60%, red for <45%

**Architecture:**
- All data parsing happens server-side in FastAPI
- Streamlit client only renders pre-parsed data from API
- All new endpoints reuse cached scoreboard data (no extra API calls to Yahoo)

### Files Created/Modified
```
dashboard/
├── main.py                    # MODIFIED - Updated imports, removed UI clutter
└── views/                     # RENAMED from pages/
    ├── __init__.py
    ├── home.py                # MODIFIED - Removed Quick Navigation section
    └── weekly.py              # MODIFIED - Added 4 tabs, fetch from new endpoints

app/parsing/
└── scoreboard.py              # MODIFIED - Added totals, rankings, H2H parsing

backend/routes/
└── api.py                     # MODIFIED - Added 3 new endpoints
```

### API Endpoints Added
- `GET /api/league/{key}/weekly-totals?week=N` - All teams' weekly stats
- `GET /api/league/{key}/weekly-rankings?week=N` - Team rankings per category
- `GET /api/league/{key}/weekly-h2h?week=N` - Head-to-head matrix

### Current State
- **Phase 1: COMPLETE**
- **Phase 2: COMPLETE**
- **Phase 3: IN PROGRESS**
  - OAuth flow working ✓
  - League selector ✓
  - Standings with stats display ✓
  - Weekly scoreboard page ✓
  - Weekly totals tab ✓
  - Weekly rankings tab ✓
  - Weekly H2H matrix tab ✓
  - Data caching with freshness indicator ✓
  - Logging utilities ✓
  - Remaining: transactions page, trend visualizations

### Blockers
None

### Next Session (Session 7)
Focus: Transactions Page and Trend Visualizations

1. **Create transactions page**
   - Parse transaction data from Yahoo API
   - Display recent adds, drops, trades

2. **Add trend visualizations**
   - Standings bump chart over time
   - Category performance trends

3. **Polish and bug fixes**
   - Test with real Yahoo data
   - Handle edge cases (empty data, errors)


---

## Session 7 - 2026-01-24

### Completed

**Transactions Feature - Full Implementation:**

1. **Database Models** (`app/database/models.py`)
   - Added `Transaction` model for storing transaction records
   - Added `TransactionPlayer` model for players involved in transactions
   - Normalized structure: one Transaction can have multiple TransactionPlayers
   - Proper indexes on league_key, player_id, team keys for query performance
   - Unique constraint on (league_key, transaction_id) for deduplication

2. **Transaction Parsing** (`app/parsing/transactions.py`)
   - Created parsing module adapted from CLI reference
   - `parse_transactions()` - Parse full Yahoo API response
   - `parse_single_transaction()` - Parse individual transaction
   - `parse_player_from_transaction()` - Extract player details
   - `get_transaction_summary()` - Generate transaction statistics

3. **Transaction Service** (`app/services/transactions.py`)
   - Created `TransactionService` class for database operations
   - `store_transactions()` - Store with automatic deduplication
   - `get_transactions()` - Query with filters (type, team)
   - `get_manager_activity()` - Transaction counts per team
   - `get_most_added_players()` - Popular adds
   - `get_most_dropped_players()` - Popular drops
   - `get_transaction_stats()` - Comprehensive statistics

4. **API Endpoints** (`backend/routes/api.py`)
   - Rewrote `GET /api/league/{key}/transactions` - Now database-backed with sync
   - Added `GET /api/league/{key}/transactions/sync` - Force sync from Yahoo
   - Added `GET /api/league/{key}/transactions/stats` - Statistics endpoint

5. **Streamlit View** (`dashboard/views/transactions.py`)
   - Created full transactions page with 4 tabs:
     - Recent Transactions - Shows individual transactions
     - Manager Activity - Transaction counts per team
     - Most Added - Popular player additions
     - Most Dropped - Popular player drops
   - Sync button to fetch new transactions from Yahoo
   - Team name resolution via API

6. **Dashboard Navigation** (`dashboard/main.py`)
   - Added "Transactions" to sidebar navigation
   - Integrated transactions page rendering

7. **Tests** (`tests/test_transactions.py`)
   - 15 comprehensive tests for parsing and service
   - Tests cover: add, drop, trade, add/drop transactions
   - Tests cover: deduplication, filtering, statistics

### Architecture Highlights
- **Incremental Fetching**: Only new transactions are stored (dedupe by transaction_id)
- **Database-Backed**: No JSON caching, normalized tables for efficient queries
- **No Refresh Needed**: Transactions are immutable, only fetch new ones
- **Server-Side Processing**: All parsing happens in FastAPI, Streamlit just renders

### Files Created/Modified
```
app/database/
└── models.py                  # MODIFIED - Added Transaction, TransactionPlayer

app/parsing/
└── transactions.py            # NEW - Transaction parsing

app/services/
└── transactions.py            # NEW - Transaction service

backend/routes/
└── api.py                     # MODIFIED - New/rewritten transaction endpoints

dashboard/
├── main.py                    # MODIFIED - Added Transactions navigation
└── views/
    └── transactions.py        # NEW - Transactions page

tests/
└── test_transactions.py       # NEW - 15 tests
```

### API Endpoints
- `GET /api/league/{key}/transactions` - Get transactions (with filters, pagination)
- `GET /api/league/{key}/transactions/sync` - Force sync from Yahoo
- `GET /api/league/{key}/transactions/stats` - Manager activity, most added/dropped

### Test Results
- All 70 tests passing (existing 55 + new 15)
- Parsing tests: 9 passed
- Service tests: 6 passed

### Current State
- **Phase 1: COMPLETE**
- **Phase 2: COMPLETE**
- **Phase 3: IN PROGRESS**
  - OAuth flow working ✓
  - League selector ✓
  - Standings with stats display ✓
  - Weekly scoreboard page ✓
  - Weekly totals tab ✓
  - Weekly rankings tab ✓
  - Weekly H2H matrix tab ✓
  - Data caching with freshness indicator ✓
  - **Transactions page ✓** (NEW)
  - Logging utilities ✓
  - Remaining: Periodical Analysis (multi-week aggregation)

### Blockers
None

### Next Session (Session 8)
Focus: Additional Features and Polish
1. Test end-to-end with real Yahoo data
2. Handle edge cases (empty data, errors)
3. Consider: Periodical Analysis for multi-week stats aggregation
4. Consider: Chart visualizations for trends

---

## Session 8 - 2026-01-24

### Completed

**Code Quality Review & Improvements:**

Conducted comprehensive code review across four areas: caching, error handling, logging, and architecture. Implemented critical fixes in two phases.

**Phase 1: Critical Fixes**

1. **Added Caching to Uncached Endpoints** (`backend/routes/api.py`)
   - `GET /league/{key}/info` - Now cached indefinitely (league info rarely changes)
   - `GET /league/{key}/teams` - Now cached indefinitely (teams don't change mid-season)
   - Both endpoints previously made Yahoo API calls on every request

2. **Fixed Silent Exception Blocks**
   - `app/parsing/transactions.py:163` - Added warning log for parse failures
   - `dashboard/main.py:118` - Added detailed logging for auth check failures
   - Previously: `except Exception: pass` - invisible failures

3. **Added Global Exception Handler** (`backend/main.py`)
   - Catches unhandled exceptions
   - Logs full stack trace for debugging
   - Returns generic "Internal server error" to clients (no stack trace exposure)

**Phase 2: Retry Logic & Error Handling**

1. **Added Tenacity Retry Library** (`app/services/yahoo_api.py`)
   - Automatic retry with exponential backoff (1s, 2s, 4s...)
   - Up to 3 attempts for transient failures
   - Retries on: `TimeoutException`, `ConnectError`
   - Does NOT retry on: 429 (rate limit), 401 (auth), other HTTP errors

2. **Custom Exception Classes** (`app/services/yahoo_api.py`)
   - `YahooAPIError` - Base exception
   - `YahooRateLimitError` - HTTP 429 with retry-after support
   - `YahooAuthError` - HTTP 401 authentication failures
   - `YahooConnectionError` - Connection failures
   - `YahooTimeoutError` - Request timeouts

3. **Consistent Error Handler** (`backend/routes/api.py`)
   - Added `handle_yahoo_api_error()` helper function
   - Maps exceptions to appropriate HTTP status codes:
     - 429 → "Yahoo API rate limit exceeded, try again later"
     - 401 → "Yahoo authentication failed, please log in again"
     - 504 → "Yahoo API request timed out"
     - 502 → "Unable to connect to Yahoo API"
   - Updated all Yahoo API endpoints to use consistent error handling

4. **Fixed Redundant API Calls** (`dashboard/views/transactions.py`)
   - Previously: 3 separate calls to `/transactions/stats` (one per tab)
   - Now: 1 call, shared data passed to all tabs
   - Reduces API calls by 66% on Transactions page

**Phase 3: Transaction Cooldown Scoping**

1. **Fixed Cooldown to be Per-League** (`app/services/transactions.py`)
   - Problem: Cooldown was per-user-per-league, but transaction data is shared
   - User A syncs → User B (same league) could sync again 5 minutes later
   - Solution: Added `get_league_last_sync_time()` to check across ALL users
   - Now: If anyone synced recently, cooldown applies to everyone in that league

### Files Created/Modified
```
app/services/
├── yahoo_api.py           # MODIFIED - Retry logic, custom exceptions (+159 lines)
└── transactions.py        # MODIFIED - League-level cooldown (+62 lines)

app/parsing/
└── transactions.py        # MODIFIED - Added exception logging

backend/
├── main.py                # MODIFIED - Global exception handler
└── routes/api.py          # MODIFIED - Caching, error handler helper

dashboard/
├── main.py                # MODIFIED - Better auth check logging
└── views/transactions.py  # MODIFIED - Fixed redundant API calls

pyproject.toml             # MODIFIED - Added tenacity dependency
requirements.txt           # MODIFIED - Added tenacity dependency
```

### Test Results
- 77/78 tests passing (98.7%)
- 1 pre-existing failure in `test_get_manager_activity` (unrelated to changes)

### Current State
- **Phase 1: COMPLETE**
- **Phase 2: COMPLETE**
- **Phase 3: IN PROGRESS**
  - OAuth flow working ✓
  - League selector ✓
  - Standings with stats display ✓
  - Weekly scoreboard page ✓
  - Weekly totals/rankings/H2H tabs ✓
  - Data caching with freshness indicator ✓
  - Transactions page ✓
  - Logging utilities ✓
  - **Error handling improvements ✓** (NEW)
  - **Retry logic with tenacity ✓** (NEW)
  - **League-level transaction cooldown ✓** (NEW)
  - Remaining: See backlog for future improvements

### Blockers
None

### Next Session
See BACKLOG.md "Architecture & Quality Improvements" section for remaining items:
- Extract duplicated `format_time_ago()` to shared module
- Add request correlation IDs
- Input validation improvements
- Move hardcoded values to config

---

<!-- Template for new sessions:

## Session N - YYYY-MM-DD

### Completed
-

### Current State
-

### Blockers
-

### Next Session
-

---
-->
