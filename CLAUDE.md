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
**Phase 2: FastAPI Backend** - COMPLETE
**Phase 3: Streamlit Dashboard** - IN PROGRESS

## Phase Order (Updated)
1. Database & Multi-User Foundation - COMPLETE
2. FastAPI Backend - COMPLETE
3. Streamlit Dashboard
4. Refactor Visualizations
5. Scheduled Data Refresh
6. Remove Hardcoded Data
7. Deployment
8. Pick-a-Winner Game (post-launch enhancement)

## Current Task
**Session 6 Focus:** Transactions Page and Polish
1. Create transactions page with recent adds, drops, trades
2. Add more visualizations (charts for stat trends, team comparisons)
3. Test with real Yahoo data and handle edge cases

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

## Adding New Packages
When a new package is needed:
1. **Add to both files** - Update `pyproject.toml` AND `requirements.txt`
2. **pyproject.toml** - Add to `dependencies` (or `[project.optional-dependencies].dev` for dev-only packages like pytest)
3. **requirements.txt** - Add with appropriate comment section
4. **Never run pip install directly** - Always update config files first, then let user install

## Testing Requirements
**IMPORTANT**: Always write tests for new features before marking them complete:
1. Create tests in `tests/` directory
2. Run tests with: `pytest tests/ -v`
3. All tests must pass before marking a task complete
4. Use `pytest` for all testing (included in dev dependencies)

## Git Commit Rules
When committing changes:
1. **Logical separation** - Group related changes into separate commits
2. **Concise messages** - Informative yet brief commit messages
3. **No co-author tags** - Do NOT add "Co-Authored-By: Claude" or similar
4. **Use conventional format** - Start with verb (Add, Fix, Update, Refactor, etc.)
