# Claude Code Context

**Read this file at the start of every session.**

## Project Summary
Web-accessible dashboard for Yahoo Fantasy Basketball with multi-user OAuth support. Building in Streamlit first, with FastAPI backend.

## Reference Repository
The original CLI tool is at: `C:\Users\darch\Projects\Yahoo_NBA_Fantasy_Hub`
- Use it for reference when adapting parsing/visualization code
- Do NOT modify that repository

## Current Phase
**Phase 1: Database & Multi-User Foundation** (Not started)

## Phase Order (Updated)
1. Database & Multi-User Foundation
2. FastAPI Backend
3. Scheduled Data Refresh (CORE - before deployment!)
4. Streamlit Dashboard
5. Refactor Visualizations
6. Remove Hardcoded Data
7. Deployment
8. Pick-a-Winner Game (post-launch enhancement)

## Current Task
Setting up project structure and documentation

## Quick Links
- [Work Plan](./work_plan.md) - High-level roadmap and architecture
- [Progress Log](./docs/PROGRESS.md) - Session-by-session progress
- [Decisions](./docs/DECISIONS.md) - Architectural decisions and rationale
- [Backlog](./docs/BACKLOG.md) - Detailed task checklist

## Critical Context
- Using SQLite for MVP (PostgreSQL later)
- Streamlit Cloud for deployment
- Keep CLI repo unchanged - copy/adapt code here
- Remove hardcoded manager names - fetch dynamically from API

## Session Start Checklist
1. Read this file
2. Check PROGRESS.md for last session's state
3. Check BACKLOG.md for next tasks
4. Continue implementation
