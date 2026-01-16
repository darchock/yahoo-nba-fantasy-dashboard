# Claude Code Context

**Read this file at the start of every session.**

## Project Summary
Web-accessible dashboard for Yahoo Fantasy Basketball with multi-user OAuth support. Building in Streamlit first, with FastAPI backend.

## Reference Repository
The original CLI tool is at: `C:\Users\darch\Projects\Yahoo_NBA_Fantasy_Hub`
- Use it for reference when adapting parsing/visualization code
- Do NOT modify that repository

## Current Phase
**Phase 1: Database & Multi-User Foundation** - COMPLETE
**Phase 2: FastAPI Backend** - Up next

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
Ready to start Phase 2: FastAPI Backend (OAuth endpoints, API routes)

## Quick Links
- [Work Plan](./work_plan.md) - High-level roadmap and architecture
- [Progress Log](./docs/PROGRESS.md) - Session-by-session progress
- [Decisions](./docs/DECISIONS.md) - Architectural decisions and rationale
- [Backlog](./docs/BACKLOG.md) - Detailed task checklist
- [Issues Log](./docs/ISSUES_LOG.md) - Resolved issues and solutions
- [OAuth Architecture](./docs/OAUTH_ARCHITECTURE.md) - Multi-user auth design

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

## Quality Checklist (Before Marking Tasks Complete)
**IMPORTANT**: Always verify these before marking any task as complete:

1. **Run the code** - Execute tests to verify runtime behavior
2. **Check Pylance/IDE errors** - Use `mcp__ide__getDiagnostics` to check for:
   - Import errors (may indicate wrong Python interpreter)
   - Type errors (fix or add `# type: ignore` with reason)
   - Deprecation warnings (use modern alternatives)
   - Unused imports (remove them)
3. **Fix real issues** - Don't just silence warnings; understand and fix root causes
4. **Re-test after fixes** - Ensure fixes didn't break anything

Common Pylance issues in this project:
- SQLAlchemy Column types vs runtime types → use `# type: ignore[return-value]`
- `datetime.utcnow()` deprecated → use `datetime.now(timezone.utc)`
- Import not resolved → VS Code needs correct Python interpreter selected

## Quick Links
- [Issues Log](./docs/ISSUES_LOG.md) - Resolved issues and solutions
