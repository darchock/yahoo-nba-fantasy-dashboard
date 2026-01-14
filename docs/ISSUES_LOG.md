# Issues Log

This document tracks issues encountered during development and their solutions.

---

## Session 1 - 2026-01-14

### Issue 1: Pylance "Import could not be resolved" errors

**Files affected:** `config.py`, `models.py`, `connection.py`, `yahoo_api.py`

**Symptoms:**
```
Import "sqlalchemy" could not be resolved
Import "dotenv" could not be resolved
Import "httpx" could not be resolved
```

**Cause:**
VS Code/Pylance was not using the project's virtual environment. It was looking at the system Python which didn't have the packages installed.

**Solution:**
1. Press `Ctrl+Shift+P` in VS Code
2. Type "Python: Select Interpreter"
3. Choose `.\venv\Scripts\python.exe`

**Lesson:** After creating a venv and installing packages, always verify VS Code is using the correct interpreter.

---

### Issue 2: `datetime.utcnow()` deprecation warnings

**Files affected:** `models.py`, `yahoo_api.py`

**Symptoms:**
```
The method "utcnow" in class "datetime" is deprecated
Use timezone-aware objects to represent datetimes in UTC
```

**Cause:**
`datetime.utcnow()` is deprecated in Python 3.12+ because it returns a naive datetime (no timezone info).

**Solution:**
Replace:
```python
from datetime import datetime
datetime.utcnow()
```

With:
```python
from datetime import datetime, timezone
datetime.now(timezone.utc)
```

For SQLAlchemy Column defaults, use a lambda:
```python
created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```

**Lesson:** Use timezone-aware datetimes from the start to avoid migration issues later.

---

### Issue 3: Aggressive `replace_all` broke property methods

**Files affected:** `models.py`

**Symptoms:**
```python
# This was incorrectly generated:
return lambda: datetime.now(timezone.utc)() >= self.expires_at
```

**Cause:**
Used `replace_all=true` on `datetime.utcnow` which replaced it everywhere, including in property methods where it should be called directly, not wrapped in a lambda.

**Solution:**
Manual fix - property methods should use direct call:
```python
@property
def is_expired(self) -> bool:
    return datetime.now(timezone.utc) >= self.expires_at
```

Column defaults should use lambda:
```python
created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```

**Lesson:** Be careful with `replace_all` - review the context of each occurrence before bulk replacing.

---

### Issue 4: SQLAlchemy Column type vs Python type mismatch

**Files affected:** `models.py`

**Symptoms:**
```
Type "ColumnElement[bool]" is not assignable to return type "bool"
```

**Cause:**
Pylance sees SQLAlchemy Column descriptors at static analysis time, not the runtime Python values. When comparing `self.expires_at` (which Pylance thinks is a Column), it infers the result is `ColumnElement[bool]` instead of `bool`.

**Solution:**
Add type ignore comments for SQLAlchemy runtime behavior:
```python
@property
def is_expired(self) -> bool:
    return datetime.now(timezone.utc) >= self.expires_at  # type: ignore[return-value]
```

**Lesson:** SQLAlchemy and type checkers don't always agree. Use `# type: ignore` with specific error codes when you're certain the runtime behavior is correct.

---

### Issue 5: Wrong return type annotation for `get_user_leagues`

**Files affected:** `yahoo_api.py`

**Symptoms:**
```
Type "Dict[str, Any]" is not assignable to return type "List[Dict[str, Any]]"
```

**Cause:**
Method was annotated to return `List[Dict[str, Any]]` but was returning the raw API response (a Dict).

**Solution:**
Instead of changing the type annotation (wrong fix), properly parse the response to return a list:
```python
async def get_user_leagues(self, sport: str = "nba") -> List[Dict[str, Any]]:
    response = await self.make_request(...)

    # Parse Yahoo's nested response structure
    leagues = []
    games = safe_get(response, "fantasy_content", "users", 0, "user", 1, "games", default={})
    # ... parsing logic ...
    return leagues
```

**Lesson:** When there's a type mismatch, fix the code to match the intended behavior, don't just change the type annotation.

---

### Issue 6: Unused imports

**Files affected:** `helpers.py`

**Symptoms:**
```
"json" is not accessed
"os" is not accessed
```

**Cause:**
Imports were copied from the CLI repo but not all functions that used them were needed.

**Solution:**
Remove unused imports:
```python
# Before
from typing import Any, Dict, List, Optional
import json
import os

# After
from typing import Any, Dict, List, Optional
```

**Lesson:** When adapting code from another project, review imports and remove unused ones.

---

## Prevention Checklist

Before marking any task complete:

- [ ] Run the code and verify it works
- [ ] Run `mcp__ide__getDiagnostics` to check for Pylance errors
- [ ] Fix actual code issues (don't just silence valid warnings)
- [ ] Re-run tests after fixes
- [ ] Remove unused imports
- [ ] Use modern Python patterns (timezone-aware datetime, etc.)
