# Task Backlog

Legend: `[ ]` pending | `[x]` done | `[~]` in progress | `[-]` skipped

---

## Phase 1: Database & Multi-User Foundation

### Project Setup
- [x] Create folder structure (app/, backend/, dashboard/, data/)
- [x] Create requirements.txt with dependencies
- [x] Create .env.example template
- [x] Set up app/config.py with environment variable loading

### Database
- [x] Create app/database/models.py (User, OAuthToken, UserLeague, CachedData)
- [x] Add Pick-a-Winner models (MatchupPrediction, PredictionResult, PredictionStandings)
- [x] Create app/database/connection.py (session management)
- [x] Test database creation and migrations

### Adapt Core Code from CLI Repo
- [x] Copy and adapt parsing helpers (safe_get, STAT_ID_TO_NAME_MAP)
- [x] Create app/services/yahoo_api.py (instance-based, per-user tokens)

---

## Phase 2: FastAPI Backend

### OAuth Flow
- [x] Create backend/main.py (FastAPI app entry)
- [x] Create backend/routes/auth.py (/login, /callback, /logout)
- [x] Test complete OAuth flow with Yahoo

### API Endpoints
- [x] Create backend/routes/api.py
- [x] GET /api/user/leagues
- [x] GET /api/league/{id}/scoreboard/{week}
- [x] GET /api/league/{id}/standings/{week}
- [x] Test all endpoints with curl/Postman

---

## Phase 3: Streamlit Dashboard

### Core Dashboard
- [x] Create dashboard/app.py (main entry)
- [x] Implement Yahoo OAuth login button
- [x] Create league selector dropdown
- [x] Create week picker
- [ ] Add "Last updated" indicator with manual refresh button

### Pages
- [x] dashboard/pages/home.py (league overview)
- [ ] dashboard/pages/weekly.py (weekly visualizations)
- [ ] dashboard/pages/trends.py (bump chart, trends)
- [ ] dashboard/pages/transactions.py (transaction analysis)

### Authentication (Added Session 3)
- [x] Implement JWT token-based auth for Streamlit
- [x] Create secure auth code exchange flow
- [x] Add AuthCode database model
- [x] Add /auth/yahoo/exchange endpoint

---

## Phase 4: Refactor Visualizations

### Convert to Plotly
- [ ] Adapt totals_table.py -> Plotly figure
- [ ] Adapt ranking_table.py -> Plotly figure
- [ ] Adapt head_to_head.py -> Plotly heatmap
- [ ] Adapt standings_bump_chart.py -> Plotly line chart
- [ ] Adapt transactions.py -> Plotly bar charts
- [ ] Copy/adapt helper functions (RTL text, color gradients)

---

## Phase 5: Scheduled Data Refresh

### Scheduler Setup
- [ ] Create app/services/scheduler.py (APScheduler with FastAPI)
- [ ] Create app/jobs/refresh_data.py (data fetching logic)
- [ ] Add job status/logs table to database

### Jobs
- [ ] Implement daily_refresh job (scores, standings for active leagues)
- [ ] Implement weekly_refresh job (full sync, cleanup old cache)
- [ ] Implement on_demand refresh (manual trigger from API)
- [ ] Test scheduler runs correctly

---

## Phase 6: Remove Hardcoded Data

- [ ] Remove MANAGER_ID_TO_NAME_MAP dependency
- [ ] Fetch team names dynamically from Yahoo API
- [ ] Update all parsing code to use dynamic names

---

## Phase 7: Deployment

- [ ] Prepare for Streamlit Cloud deployment
- [ ] Set up environment variables in Streamlit Cloud
- [ ] Configure HTTPS callback URL for OAuth
- [ ] Ensure scheduler runs as background process
- [ ] Test on mobile devices
- [ ] Test multi-league functionality

---

## Phase 8: Pick-a-Winner Game (Post-Launch)

### Backend
- [ ] Create app/services/predictions.py (prediction logic)
- [ ] Create backend/routes/predictions.py (API endpoints)
- [ ] GET /api/league/{id}/matchups/{week}
- [ ] POST /api/league/{id}/predictions/{week}
- [ ] GET /api/league/{id}/predictions/{week}
- [ ] GET /api/league/{id}/prediction-standings

### Frontend
- [ ] Create dashboard/pages/pick_winner.py (matchup cards, team selection)
- [ ] Add countdown timer to prediction deadline
- [ ] Create dashboard/pages/prediction_standings.py (leaderboard)
- [ ] Add results view (correct/incorrect indicators)
- [ ] Track streaks and accuracy percentages

---

## Discovered During Development
<!-- Add tasks discovered during implementation here -->

---
