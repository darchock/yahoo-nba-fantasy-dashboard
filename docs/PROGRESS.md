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
  - Create `dashboard/app.py` (main Streamlit entry)
  - Implement Yahoo OAuth login button
  - Create league selector dropdown
  - Create week picker
  - Display basic league data

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
