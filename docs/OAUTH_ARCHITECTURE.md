# OAuth & Multi-User Architecture

This document explains how authentication and user identity work in the Yahoo Fantasy Dashboard.

---

## User Identity: Yahoo GUID vs Manager ID

### The Problem
In Yahoo Fantasy leagues, each team has a "manager ID" (1, 2, 3, etc.) that's specific to that league. Two different people could both be "manager 1" in their respective leagues.

### Our Solution
We identify users by their **Yahoo GUID** (Global Unique Identifier), not by league-specific manager IDs.

- `yahoo_guid`: Globally unique across all of Yahoo, tied to the user's Yahoo account
- Manager ID: League-specific position number (not unique across leagues)

### Database Design
```
User (yahoo_guid: unique globally)
  └── OAuthToken (one token set per user)
  └── UserLeague (user_id + league_key unique constraint)
        - Same user can be in multiple leagues
        - Different users are always separate User records
```

### Example
If Alice and Bob are both in League A, and Alice is also in League B:
- Alice: 1 User record, 1 OAuthToken, 2 UserLeague records
- Bob: 1 User record, 1 OAuthToken, 1 UserLeague record

---

## OAuth Credentials: One App, Many Users

### Key Concept
Users do NOT need their own Yahoo Developer app. The dashboard operator has ONE app that serves all users.

### Credential Types

| Component | Who Has It | Scope | Storage |
|-----------|-----------|-------|---------|
| `client_id` | Dashboard operator (one set) | Entire application | `.env` file |
| `client_secret` | Dashboard operator (one set) | Entire application | `.env` file |
| `access_token` | Per user | That user's Yahoo data | `oauth_tokens` table |
| `refresh_token` | Per user | That user's Yahoo data | `oauth_tokens` table |

### OAuth Flow

```
User clicks "Login with Yahoo"
      │
      ▼
Redirect to Yahoo (using dashboard's client_id)
      │
      ▼
User logs into THEIR Yahoo account
      │
      ▼
Yahoo prompts: "Allow [Dashboard App] to access your fantasy data?"
      │
      ▼
User clicks "Allow"
      │
      ▼
Yahoo redirects back with authorization code
      │
      ▼
Backend exchanges code for tokens (using client_id + client_secret)
      │
      ▼
Tokens stored in oauth_tokens table (linked to user)
      │
      ▼
Tokens grant access to ALL of that user's leagues
```

### What This Means

1. **For the dashboard operator:**
   - Register ONE app at [Yahoo Developer Network](https://developer.yahoo.com/)
   - Store `client_id` and `client_secret` in environment variables
   - These credentials never change (unless you regenerate them)

2. **For end users:**
   - No developer setup required
   - Just click "Login with Yahoo" and authorize the app
   - Works exactly like "Login with Google" on any website

3. **Token scope:**
   - Each user's tokens give access only to THEIR fantasy data
   - The API returns only leagues the authenticated user belongs to
   - Users cannot see other users' leagues or data

---

## Security Considerations

1. **Client secret**: Never expose in frontend code or commit to git
2. **Access tokens**: Short-lived (typically 1 hour), stored encrypted in production
3. **Refresh tokens**: Long-lived, used to get new access tokens without re-login
4. **Token storage**: Per-user in database, never shared between users

---

## Related Files

- `app/database/models.py` - User, OAuthToken, UserLeague models
- `app/config.py` - Environment variable loading (client_id, client_secret)
- `backend/routes/auth.py` - OAuth endpoints (to be implemented in Phase 2)
