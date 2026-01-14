# Task Backlog

Legend: `[ ]` pending | `[x]` done | `[~]` in progress | `[-]` skipped

---

## Phase 1: Database & Multi-User Foundation

### Project Setup
- [ ] Create folder structure (app/, backend/, dashboard/, data/)
- [ ] Create requirements.txt with dependencies
- [ ] Create .env.example template
- [ ] Set up app/config.py with environment variable loading

### Database
- [ ] Create app/database/models.py (User, OAuthToken, UserLeague, CachedData)
- [ ] Add Pick-a-Winner models (MatchupPrediction, PredictionResult, PredictionStandings)
- [ ] Create app/database/connection.py (session management)
- [ ] Test database creation and migrations

### Adapt Core Code from CLI Repo
- [ ] Copy and adapt parsing helpers (safe_get, STAT_ID_TO_NAME_MAP)
- [ ] Create app/services/yahoo_api.py (instance-based, per-user tokens)

---

## Phase 2: FastAPI Backend

### OAuth Flow
- [ ] Create backend/main.py (FastAPI app entry)
- [ ] Create backend/routes/auth.py (/login, /callback, /logout)
- [ ] Test complete OAuth flow with Yahoo

### API Endpoints
- [ ] Create backend/routes/api.py
- [ ] GET /api/user/leagues
- [ ] GET /api/league/{id}/scoreboard/{week}
- [ ] GET /api/league/{id}/standings/{week}
- [ ] Test all endpoints with curl/Postman

---

## Phase 3: Scheduled Data Refresh (CORE)

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

## Phase 4: Streamlit Dashboard

### Core Dashboard
- [ ] Create dashboard/app.py (main entry)
- [ ] Implement Yahoo OAuth login button
- [ ] Create league selector dropdown
- [ ] Create week picker
- [ ] Add "Last updated" indicator with manual refresh button

### Pages
- [ ] dashboard/pages/home.py (league overview)
- [ ] dashboard/pages/weekly.py (weekly visualizations)
- [ ] dashboard/pages/trends.py (bump chart, trends)
- [ ] dashboard/pages/transactions.py (transaction analysis)

---

## Phase 5: Refactor Visualizations

### Convert to Plotly
- [ ] Adapt totals_table.py -> Plotly figure
- [ ] Adapt ranking_table.py -> Plotly figure
- [ ] Adapt head_to_head.py -> Plotly heatmap
- [ ] Adapt standings_bump_chart.py -> Plotly line chart
- [ ] Adapt transactions.py -> Plotly bar charts
- [ ] Copy/adapt helper functions (RTL text, color gradients)

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
