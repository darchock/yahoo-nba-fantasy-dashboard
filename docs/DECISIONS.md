# Architectural Decisions

This document records key decisions made during development and the reasoning behind them.

---

## Decision 1: New Repository vs Modifying Existing

**Date:** 2026-01-14
**Status:** Decided

**Context:**
Could either modify Yahoo_NBA_Fantasy_Hub to add web functionality or create a new repository.

**Decision:**
Create new repository (yahoo-nba-fantasy-dashboard).

**Rationale:**
- Zero risk to working CLI tool
- Clean architecture designed for web from start
- Fresh git history, no legacy baggage
- Can merge repos later if desired

---

## Decision 2: Streamlit MVP vs Full React App

**Date:** 2026-01-14
**Status:** Decided

**Context:**
Need a web frontend. Options: Streamlit (Python-only, fast) vs React (more customizable, more work).

**Decision:**
Streamlit first, migrate to React later if needed.

**Rationale:**
- Faster time to working product
- Python-only stack (no JS learning curve)
- Streamlit Cloud offers free hosting with HTTPS
- Can always migrate if customization needs exceed Streamlit's capabilities

---

## Decision 3: SQLite vs PostgreSQL

**Date:** 2026-01-14
**Status:** Decided

**Context:**
Need database for users, tokens, cached data.

**Decision:**
SQLite for MVP, migrate to PostgreSQL when scaling.

**Rationale:**
- Zero setup, file-based
- Works fine for single-server deployment
- SQLAlchemy makes migration straightforward
- PostgreSQL adds complexity not needed for MVP

---

## Decision 4: Documentation Strategy

**Date:** 2026-01-14
**Status:** Updated

**Context:**
Multi-session work requires context persistence between Claude Code sessions.

**Decision:**
Markdown files in repo (CLAUDE.md, docs/*.md), tracked in git (NOT gitignored).

**Rationale:**
- Claude can read files at session start
- Full revision history for documentation changes
- Backed up with the code
- Initially considered gitignoring, but revision history is valuable
- Can make repo private if concerned about visibility
- Searchable in IDE

---

## Decision 5: Quality Verification Process

**Date:** 2026-01-14
**Status:** Decided

**Context:**
Code that runs successfully may still have IDE/type checker errors, deprecation warnings, or type annotation issues.

**Decision:**
Before marking any task complete, always run both runtime tests AND check Pylance/IDE diagnostics.

**Rationale:**
- Runtime tests only catch execution errors
- Pylance catches type mismatches, deprecated APIs, unused code
- Fixing issues early prevents technical debt
- Documented in CLAUDE.md Quality Checklist and docs/ISSUES_LOG.md

---

## Decision 6: Phase Order - Dashboard Before Scheduler

**Date:** 2026-01-16
**Status:** Decided

**Context:**
Original plan had Scheduled Data Refresh (Phase 3) before Streamlit Dashboard (Phase 4). This meant building automation before having a visible product.

**Decision:**
Reorder phases: Dashboard and Visualizations come before Scheduler.

**New order:**
1. Database & Multi-User Foundation (done)
2. FastAPI Backend
3. Streamlit Dashboard
4. Refactor Visualizations
5. Scheduled Data Refresh
6. Remove Hardcoded Data
7. Deployment
8. Pick-a-Winner Game

**Rationale:**
- Get a visible, usable product sooner
- Can test and iterate on UI with manually-refreshed or mock data
- Scheduler is an enhancement, not a blocker for basic functionality
- Easier to demonstrate progress to stakeholders

---

## Decision 7: Self-Signed SSL for Local Development

**Date:** 2026-01-16
**Status:** Decided

**Context:**
Yahoo OAuth requires HTTPS for all redirect URIs, including localhost development. Options considered:
1. Use ngrok to create public HTTPS URL
2. Self-signed SSL certificate with uvicorn
3. Reverse proxy with nginx/caddy

**Decision:**
Use self-signed SSL certificate for local development.

**Implementation:**
```bash
# Generate certificate
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "//CN=localhost"

# Run uvicorn with SSL
uvicorn backend.main:app --host localhost --port 8080 --ssl-keyfile key.pem --ssl-certfile cert.pem --reload
```

**Rationale:**
- Simplest solution that works locally
- No external dependencies (ngrok requires account)
- Matches Yahoo's registered redirect URI (`https://localhost:8080/callback`)
- Certificate files gitignored for security
- Can revisit for production (use real certificates)

---

## Decision 8: Configurable Frontend Redirect URL

**Date:** 2026-01-16
**Status:** Decided

**Context:**
After OAuth callback, need to redirect user somewhere. This destination differs by environment:
- Development: API endpoint to verify auth works
- Production: Streamlit dashboard URL

**Decision:**
Add `FRONTEND_URL` environment variable for configurable post-OAuth redirect.

**Configuration:**
```env
# Development
FRONTEND_URL=https://localhost:8080/auth/yahoo/me

# Production (Streamlit Cloud)
FRONTEND_URL=https://your-app.streamlit.app
```

**Rationale:**
- Single code path, environment-driven behavior
- Easy to change without code modifications
- Documented in `.env.example`

---

## Decision 9: Cookie-Based Session Persistence

**Date:** 2026-01-29
**Status:** Decided

**Context:**
JWT tokens stored in Streamlit's `st.session_state` are lost on every page refresh, forcing users to re-login each time they refresh the dashboard.

**Decision:**
Implement browser cookie-based sessions:
1. Create `UserSession` database model with 30-day expiry
2. Store encrypted session ID in browser cookie via `streamlit-cookies-manager`
3. On page load, validate session with backend and restore JWT token
4. On logout, clear both cookie and server-side session

**Rationale:**
- Standard web pattern for session persistence
- Survives page refreshes without re-authentication
- Secure: session ID is encrypted in cookie, validated server-side
- Configurable expiry via `SESSION_EXPIRE_DAYS` environment variable
- `last_activity` timestamp extends active sessions automatically

**Alternatives Considered:**
- JWT-only: Doesn't survive page refresh in Streamlit
- LocalStorage: Not accessible from Streamlit Python code
- Query parameters: Insecure, visible in URL

---

## Decision 10: Lazy Refresh Caching Strategy

**Date:** 2026-01-29
**Status:** Decided

**Context:**
The original 15-minute TTL for cached data was too aggressive and didn't match how fantasy data actually changes. Yahoo Fantasy data typically updates overnight, not throughout the day.

**Decision:**
Implement "lazy refresh at 6 AM Eastern" caching strategy:
- First request after 6 AM Eastern: Fetch fresh data from Yahoo
- Subsequent requests same day: Use cached data
- Completed weeks/matchups: Never re-fetch (cache forever with `is_complete=True`)
- `refresh=true` parameter still available for manual override

**Implementation:**
```python
def should_refresh_cache(fetched_at: datetime) -> bool:
    """Return True if fetched_at was BEFORE today's 6 AM Eastern."""
    eastern = pytz.timezone("America/New_York")
    now_eastern = datetime.now(eastern)

    today_6am = now_eastern.replace(hour=6, minute=0, second=0, microsecond=0)
    if now_eastern < today_6am:
        refresh_boundary = today_6am - timedelta(days=1)
    else:
        refresh_boundary = today_6am

    return fetched_at.astimezone(eastern) < refresh_boundary
```

**Rationale:**
- Matches fantasy data lifecycle (games finish overnight, stats finalize by morning)
- Simpler logic than TTL-based expiration
- No wasted API calls for data that hasn't changed
- 6 AM Eastern chosen because NBA games typically end by 1 AM ET
- Configurable via `CACHE_REFRESH_HOUR` and `CACHE_REFRESH_TIMEZONE`

**Alternatives Considered:**
- TTL-based (15 minutes): Too aggressive, wasted API calls
- Scheduled refresh: More complex, requires background jobs
- Manual refresh only: Poor UX, stale data

---

<!-- Template for new decisions:

## Decision N: Title

**Date:** YYYY-MM-DD
**Status:** Proposed / Decided / Superseded

**Context:**
What is the issue?

**Decision:**
What was decided?

**Rationale:**
- Why this choice?

---
-->
