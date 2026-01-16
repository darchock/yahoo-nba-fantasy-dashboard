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
