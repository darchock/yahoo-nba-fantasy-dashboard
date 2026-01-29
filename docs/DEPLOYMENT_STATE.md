# Deployment State - Railway Setup

**Date:** 2026-01-29

## Status: Ready for Railway Deployment

All code changes for Railway have been completed and committed (pending your push).

## Completed Code Changes

1. **`app/config.py`** - Handles Railway's `postgres://` → `postgresql://` URL conversion
2. **`backend/main.py`** - Added `*.up.railway.app` to CORS origins
3. **`.streamlit/config.toml`** - Removed hardcoded port/address
4. **`railway.toml`** - Railway deployment config
5. **`RAILWAY_DEPLOY.md`** - Full step-by-step deployment guide

## Next Steps

1. **Commit and push:**
   ```bash
   git add .
   git commit -m "Add Railway deployment configuration"
   git push origin main
   ```

2. **Follow `RAILWAY_DEPLOY.md`** for Railway setup

## Quick Reference - Railway Services to Create

### 1. PostgreSQL Database
- Add via Railway dashboard (one-click)

### 2. API Service (FastAPI)
- **Start command:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Required env vars:**
  - `DATABASE_URL` (link from PostgreSQL)
  - `YAHOO_CLIENT_ID`
  - `YAHOO_CLIENT_SECRET`
  - `YAHOO_REDIRECT_URI` = `https://<api-url>/callback`
  - `APP_SECRET_KEY`
  - `FRONTEND_URL` = `https://<dashboard-url>`
  - `DEBUG` = `false`

### 3. Dashboard Service (Streamlit)
- **Start command:** `streamlit run dashboard/main.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`
- **Required env vars:**
  - `API_BASE_URL` = `https://<api-url>`
  - `APP_SECRET_KEY` (same as API)
  - `VERIFY_SSL` = `true`

## AWS Cleanup Reminder

Don't forget to terminate and clean up AWS resources to avoid charges:
- Terminate EC2 instances
- Release Elastic IPs
- Delete security groups (optional)
