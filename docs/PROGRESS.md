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
