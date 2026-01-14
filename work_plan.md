# Yahoo Fantasy Hub - Interactive Dashboard Plan

## Goal
Build a web-accessible dashboard for Yahoo Fantasy Basketball that:
- League members can access from any device (mobile-friendly)
- Supports multiple Yahoo Fantasy leagues (not just yours)
- Handles per-user Yahoo OAuth authentication

## Repository Strategy
**New Repository**: `yahoo-fantasy-dashboard` (or similar name)
- Build the web app from scratch in a fresh repo
- Reference and copy useful code from `Yahoo_NBA_Fantasy_Hub` as needed
- Keep `Yahoo_NBA_Fantasy_Hub` as the working CLI tool (unchanged)

**Benefits**:
- Zero risk to current CLI workflow
- Clean architecture designed for web from the start
- Fresh git history, no legacy baggage
- Can deprecate CLI or merge repos later if desired

## Chosen Approach: Streamlit MVP → Full Web App Later

**Phase 1**: Build a Streamlit-based dashboard (Python-only, fast to deploy)
**Phase 2**: Migrate to FastAPI + React if needed for customization/scale

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Streamlit Frontend                      │
│  (Dashboard UI, Visualizations, League Selector, Mobile)    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                         │
│  (REST API, OAuth Callbacks, Background Jobs)               │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                           │
┌───────────────┐                         ┌─────────────────┐
│   PostgreSQL  │                         │  Yahoo Fantasy  │
│   Database    │                         │      API        │
│ (Users,Tokens,│                         │                 │
│  LeagueData)  │                         │                 │
└───────────────┘                         └─────────────────┘
```

---

## Implementation Phases

### Phase 1: Database & Multi-User Foundation
**Files to create/modify:**
- `database/models.py` - SQLAlchemy models (User, OAuthToken, League, CachedData)
- `database/connection.py` - Database connection setup
- `config.py` - Move secrets to environment variables
- `yahoo_api_handler.py` - Refactor to instance-based (per-user tokens)

**Database Schema:**
```
users: id, email, display_name, created_at
oauth_tokens: id, user_id, access_token, refresh_token, expires_at
user_leagues: id, user_id, league_key, league_name, sport, season
cached_data: id, league_key, week, data_type, json_data, fetched_at

# Pick-a-Winner Game Tables
matchup_predictions: id, user_id, league_key, week, matchup_id, predicted_winner_team_id, created_at
prediction_results: id, prediction_id, actual_winner_team_id, is_correct, points_earned
prediction_standings: id, user_id, league_key, total_correct, total_predictions, current_streak
```

### Phase 2: FastAPI Backend
**Files to create:**
- `backend/app.py` - FastAPI application
- `backend/routes/auth.py` - Yahoo OAuth endpoints (/login, /callback, /logout)
- `backend/routes/api.py` - Data endpoints (/leagues, /scoreboard/{week}, /standings/{week})
- `backend/services/yahoo_service.py` - Refactored Yahoo API calls (per-user)

**Key Endpoints:**
```
GET  /auth/yahoo/login     → Redirect to Yahoo OAuth
GET  /auth/yahoo/callback  → Handle OAuth code, store token
GET  /api/user/leagues     → List user's Yahoo Fantasy leagues
GET  /api/league/{id}/scoreboard/{week}
GET  /api/league/{id}/standings/{week}
GET  /api/league/{id}/visualizations/{week}/{type}
```

### Phase 3: Scheduled Data Refresh
**Purpose:** Keep dashboard data fresh - this is CORE functionality, not optional

**Files to create:**
- `app/services/scheduler.py` - APScheduler job definitions
- `app/jobs/refresh_data.py` - Data fetching logic

**Jobs:**
```
daily_refresh:    Fetch latest scores, standings for active leagues
weekly_refresh:   Full data sync, cleanup old cached data
on_demand:        Manual refresh trigger from dashboard
```

**Implementation:**
- Use APScheduler with FastAPI integration
- Run jobs during off-peak hours (e.g., 4 AM)
- Store job status/logs in database
- Dashboard shows "Last updated: X hours ago"

### Phase 4: Streamlit Dashboard
**Files to create:**
- `dashboard/app.py` - Main Streamlit app
- `dashboard/pages/home.py` - League overview
- `dashboard/pages/weekly.py` - Weekly visualizations
- `dashboard/pages/trends.py` - Multi-week bump chart, trends
- `dashboard/pages/transactions.py` - Transaction analysis
- `dashboard/components/charts.py` - Plotly versions of visualizations

**Features:**
- Yahoo OAuth login button
- League selector dropdown (user's leagues)
- Week picker
- Interactive Plotly charts (replace static PNGs)
- Mobile-responsive layout
- "Last updated" indicator with manual refresh button

### Phase 5: Refactor Existing Visualizations
**Files to modify:**
- `visualization/totals_table.py` → Return Plotly figure or DataFrame
- `visualization/ranking_table.py` → Return Plotly figure
- `visualization/head_to_head.py` → Return Plotly heatmap
- `visualization/standings_bump_chart.py` → Return Plotly line chart
- `visualization/transactions.py` → Return Plotly bar charts

**Changes:**
- Add optional `return_figure=True` parameter to each function
- Keep backward compatibility for CLI usage
- Replace matplotlib with Plotly for interactivity

### Phase 6: Remove Hardcoded League Data
**Files to modify:**
- `parsing_responses/consts.py` - Remove `MANAGER_ID_TO_NAME_MAP`
- All parsing files - Fetch team names from API response dynamically

### Phase 7: Deployment
**Options:**
- Streamlit Cloud (free tier, easiest)
- Railway / Render (FastAPI + Streamlit)
- Self-hosted VPS

**Requirements:**
- Environment variables for OAuth credentials
- PostgreSQL database (or SQLite for MVP)
- HTTPS for OAuth callback
- Scheduler running as background process

### Phase 8: Pick-a-Winner Game (Post-Launch Enhancement)
**Purpose:** Playful side-game to increase engagement

**Features:**
- Before each week's matchups lock, users pick winners for all matchups
- After matchups complete, calculate correct predictions
- Separate leaderboard/standings for the prediction game
- Track streaks, accuracy percentages

**Files to create:**
- `app/services/predictions.py` - Prediction logic
- `backend/routes/predictions.py` - Prediction API endpoints
- `dashboard/pages/pick_winner.py` - Prediction UI
- `dashboard/pages/prediction_standings.py` - Game leaderboard

**Key Endpoints:**
```
GET  /api/league/{id}/matchups/{week}         → Get matchups for picking
POST /api/league/{id}/predictions/{week}      → Submit predictions
GET  /api/league/{id}/predictions/{week}      → Get user's predictions
GET  /api/league/{id}/prediction-standings    → Game leaderboard
```

**UI Components:**
- Matchup cards with team selection
- Countdown timer to prediction deadline
- Results view (correct/incorrect indicators)
- Leaderboard with streaks and accuracy

---

## Critical Files Summary

### Files to Create
| File | Purpose |
|------|---------|
| `database/models.py` | SQLAlchemy ORM models |
| `database/connection.py` | DB session management |
| `backend/app.py` | FastAPI entry point |
| `backend/routes/auth.py` | OAuth flow endpoints |
| `backend/routes/api.py` | Data API endpoints |
| `backend/routes/predictions.py` | Pick-a-Winner game endpoints |
| `dashboard/app.py` | Streamlit dashboard |
| `dashboard/pages/pick_winner.py` | Prediction submission UI |
| `dashboard/pages/prediction_standings.py` | Game leaderboard |
| `app/services/scheduler.py` | APScheduler job definitions |
| `app/services/predictions.py` | Prediction game logic |
| `app/jobs/refresh_data.py` | Scheduled data fetching |

### Files to Modify
| File | Changes |
|------|---------|
| `config.py` | Use env vars, remove hardcoded secrets |
| `yahoo_api_handler.py` | Instance-based with per-user tokens |
| `parsing_responses/consts.py` | Remove hardcoded manager names |
| `visualization/*.py` | Add Plotly return option |

---

## Verification Plan
1. **Database**: Run migrations, verify tables created
2. **OAuth Flow**: Complete Yahoo login, verify token stored in DB
3. **API Endpoints**: Test each endpoint with Postman/curl
4. **Dashboard**: Load Streamlit app, login, view visualizations
5. **Mobile**: Test responsive layout on phone/tablet
6. **Multi-League**: Add second test league, verify data isolation
7. **Scheduler**: Verify jobs run on schedule, data refreshes correctly
8. **Pick-a-Winner**: Submit predictions, verify scoring after matchups complete

---

## Open Questions (Resolved)
- [x] Streamlit vs Full React → **Streamlit first**
- [x] Single league vs multi-league → **Multi-league from start**
- [x] Tech learning curve acceptable → **Yes, open to learning**

## Final Decisions
- **Repository**: New repo (`yahoo-fantasy-dashboard`), keep CLI repo intact
- **Deployment**: Streamlit Cloud (free tier, easy HTTPS)
- **Database**: SQLite for MVP (migrate to PostgreSQL when scaling)
- **Static PNG**: Keep as fallback for CLI usage and sharing

---

## Code to Reuse from Yahoo_NBA_Fantasy_Hub

### Copy & Adapt
| Original File | What to Reuse |
|---------------|---------------|
| `yahoo_api_handler.py` | OAuth flow logic, API request structure (refactor to instance-based) |
| `parsing_responses/*.py` | Parsing logic for scoreboard, standings, transactions |
| `parsing_responses/consts.py` | `STAT_ID_TO_NAME_MAP`, `safe_get()` helper |
| `visualization/*.py` | Chart logic (convert from matplotlib to Plotly) |
| `visualization/_helpers.py` | RTL text handling, color gradient functions |

### Do NOT Copy (Replace with New Implementation)
| Original | Replacement |
|----------|-------------|
| `token_manager.py` (file-based) | Database-backed token storage |
| `config.py` (hardcoded secrets) | Environment variables |
| `main.py` (CLI entry point) | Streamlit app + FastAPI backend |
| `MANAGER_ID_TO_NAME_MAP` | Dynamic fetch from Yahoo API |

---

## New Repository Structure

```
yahoo-fantasy-dashboard/
├── .env.example              # Template for environment variables
├── .gitignore
├── requirements.txt
├── README.md
│
├── app/                      # Main application
│   ├── __init__.py
│   ├── config.py             # Settings from env vars
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py         # SQLAlchemy models
│   │   └── connection.py     # DB session management
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── yahoo_api.py      # Refactored Yahoo API handler
│   │   ├── auth.py           # OAuth flow service
│   │   ├── scheduler.py      # APScheduler setup
│   │   └── predictions.py    # Pick-a-Winner game logic
│   │
│   ├── jobs/
│   │   ├── __init__.py
│   │   └── refresh_data.py   # Scheduled data refresh job
│   │
│   ├── parsing/
│   │   ├── __init__.py
│   │   ├── scoreboard.py     # Adapted from original
│   │   ├── standings.py
│   │   ├── transactions.py
│   │   └── helpers.py        # safe_get, constants
│   │
│   └── visualization/
│       ├── __init__.py
│       ├── charts.py         # Plotly chart generators
│       └── helpers.py        # Color gradients, RTL text
│
├── backend/                  # FastAPI backend
│   ├── __init__.py
│   ├── main.py               # FastAPI app entry
│   └── routes/
│       ├── auth.py           # OAuth endpoints
│       └── api.py            # Data endpoints
│
├── dashboard/                # Streamlit frontend
│   ├── app.py                # Main Streamlit entry
│   ├── pages/
│   │   ├── home.py
│   │   ├── weekly.py
│   │   ├── trends.py
│   │   └── transactions.py
│   └── components/
│       └── charts.py
│
└── data/                     # SQLite DB, cached files
    └── .gitkeep
```

---

## Next Steps (When Starting Implementation)

1. Create new GitHub repository
2. Initialize with Python project structure
3. Set up virtual environment and requirements.txt
4. Copy and adapt core parsing/visualization code
5. Implement database models
6. Build OAuth flow with FastAPI
7. Create Streamlit dashboard
8. Deploy to Streamlit Cloud
