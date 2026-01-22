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

---

## Session 2 - 2026-01-16

### Issue 7: Yahoo OAuth requires HTTPS for redirect URI

**Symptoms:**
Yahoo Developer Console rejected `http://localhost:8000/auth/yahoo/callback` - alert stated redirect URI must be HTTPS.

**Cause:**
Yahoo OAuth security requirement - all redirect URIs must use HTTPS, even for localhost development.

**Solution:**
1. Generate self-signed SSL certificate:
   ```bash
   openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "//CN=localhost"
   ```
2. Run uvicorn with SSL:
   ```bash
   uvicorn backend.main:app --host localhost --port 8080 --ssl-keyfile key.pem --ssl-certfile cert.pem --reload
   ```
3. Update `.env` to match Yahoo's registered redirect URI:
   ```
   YAHOO_REDIRECT_URI=https://localhost:8080/callback
   ```
4. Add `*.pem` to `.gitignore`

**Lesson:** Check OAuth provider requirements early. Yahoo requires HTTPS even for development.

---

### Issue 8: Missing `itsdangerous` dependency for SessionMiddleware

**Symptoms:**
```
ModuleNotFoundError: No module named 'itsdangerous'
```

**Cause:**
Starlette's SessionMiddleware depends on `itsdangerous` for signing session cookies, but it wasn't in requirements.txt.

**Solution:**
Add to requirements.txt:
```
itsdangerous>=2.1.0
```

**Lesson:** Test imports after adding new middleware to catch missing transitive dependencies.

---

### Issue 9: Timezone-naive vs timezone-aware datetime comparison

**Symptoms:**
```
TypeError: can't compare offset-naive and offset-aware datetimes
```
Error occurred in `OAuthToken.is_expired` property when comparing `datetime.now(timezone.utc)` with `self.expires_at`.

**Cause:**
SQLite stores datetimes without timezone info (naive). When reading back, `expires_at` is naive, but we compare with `datetime.now(timezone.utc)` which is timezone-aware.

**Solution:**
Handle both naive and aware datetimes in the property:
```python
@property
def is_expired(self) -> bool:
    if self.expires_at is None:
        return True
    expires = self.expires_at
    if expires.tzinfo is None:
        # Assume UTC if naive
        expires = expires.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= expires
```

**Lesson:** SQLite doesn't preserve timezone info. Always handle potential naive datetimes when reading from database.

---

### Issue 10: Yahoo doesn't return user GUID with `fspt-r` scope only

**Symptoms:**
```
{"detail":"Could not get Yahoo user identifier from token response"}
```

**Cause:**
Initially used `openid fspt-r` scope expecting Yahoo to return `xoauth_yahoo_guid` in token response. Changed to `fspt-r` only (matching CLI app), but then GUID wasn't in response.

**Solution:**
After token exchange, make a separate API call to fetch user info:
```python
response = await client.get(
    "https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1",
    headers={"Authorization": f"Bearer {token_data['access_token']}"},
    params={"format": "json"},
)
yahoo_guid = safe_get(response.json(), "fantasy_content", "users", "0", "user", 0, "guid")
```

**Lesson:** Don't assume OAuth token responses contain all user info. May need additional API calls.

---

## Session 3 - 2026-01-20

### Issue 11: Session-based auth doesn't work across separate services

**Symptoms:**
Streamlit (port 8501) couldn't access FastAPI's session-based auth (port 8080) - API calls returned 401 Unauthorized.

**Cause:**
FastAPI's SessionMiddleware stores session data in cookies scoped to the FastAPI domain. When Streamlit's Python code makes HTTP requests to FastAPI, it doesn't have access to the browser's cookies.

**Solution:**
Implemented dual authentication:
1. **JWT tokens** for Streamlit/API clients (stateless, passed in `Authorization: Bearer` header)
2. **Session cookies** kept for direct browser access (Swagger UI, testing)

Added secure auth code exchange flow:
- OAuth callback generates short-lived auth code (60 sec, single-use, stored in DB)
- Redirect to Streamlit with code in URL (not JWT - security)
- Streamlit exchanges code for JWT via API call
- JWT stored in `st.session_state`

**Lesson:** When building separate frontend/backend services, use token-based auth instead of session cookies.

---

### Issue 12: SSL certificate errors with self-signed certs

**Symptoms:**
```
ERR_SSL_PROTOCOL_ERROR
```
Browser refused to load `https://localhost:8080`.

**Cause:**
Self-signed certificate was malformed or generated with wrong parameters.

**Solution:**
Regenerate certificate with proper parameters:
```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes -subj "//CN=localhost"
```
Note: Double slash `//CN=localhost` needed on Windows/Git Bash to prevent path conversion.

**Lesson:** On Windows with Git Bash, escape forward slashes in OpenSSL commands.

---

### Issue 13: FastAPI dependency injection not working when calling function directly

**Symptoms:**
```
AttributeError: 'Depends' object has no attribute 'credentials'
```

**Cause:**
`require_auth` function called `get_current_user(request, db)` directly, bypassing FastAPI's dependency injection. The `credentials` parameter (which has `= Depends(bearer_scheme)`) received the `Depends` object itself instead of the resolved value.

**Solution:**
Change `require_auth` to use `Depends()`:
```python
# Before (wrong)
def require_auth(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)  # Bypasses DI!

# After (correct)
def require_auth(user: Optional[User] = Depends(get_current_user)) -> User:
    if not user:
        raise HTTPException(status_code=401)
    return user
```

**Lesson:** Never call FastAPI dependency functions directly. Always use `Depends()` to let FastAPI handle injection.

---

### Issue 14: Module import errors when running Streamlit

**Symptoms:**
```
ModuleNotFoundError: No module named 'dashboard'
```

**Cause:**
When running `streamlit run dashboard/main.py`, Python doesn't know about the project's package structure. The `dashboard`, `app`, and `backend` folders aren't recognized as importable packages.

**Solution:**
Create `pyproject.toml` and install package in development mode:
```bash
pip install -e .
```

This registers the project folders as importable packages without copying files.

**Lesson:** For projects with multiple packages that import each other, use `pyproject.toml` and `pip install -e .` instead of `sys.path` hacks.

---

## Prevention Checklist

Before marking any task complete:

- [ ] Run the code and verify it works
- [ ] Run `mcp__ide__getDiagnostics` to check for Pylance errors
- [ ] Fix actual code issues (don't just silence valid warnings)
- [ ] Re-run tests after fixes
- [ ] Remove unused imports
- [ ] Use modern Python patterns (timezone-aware datetime, etc.)
