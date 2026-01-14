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
**Status:** Decided

**Context:**
Multi-session work requires context persistence between Claude Code sessions.

**Decision:**
Markdown files in repo (CLAUDE.md, docs/*.md), gitignored.

**Rationale:**
- Claude can read files at session start
- Version controlled locally but not pushed (private notes)
- No external dependencies (vs Trello)
- Searchable in IDE

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
