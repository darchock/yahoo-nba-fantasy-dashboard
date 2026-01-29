# Railway Deployment Guide

Deploy the Yahoo Fantasy Dashboard (FastAPI + Streamlit + PostgreSQL) on Railway.

## Prerequisites

- GitHub account with this repo pushed
- Railway account (https://railway.app)

## Step 1: Create Railway Project

1. Go to https://railway.app and log in
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Authorize Railway to access your GitHub
5. Select this repository

## Step 2: Add PostgreSQL Database

1. In your Railway project, click **"New"**
2. Select **"Database" → "Add PostgreSQL"**
3. Railway will provision a PostgreSQL instance
4. Click on the PostgreSQL service to see connection details
5. Note: Railway automatically provides `DATABASE_URL` to linked services

## Step 3: Create the API Service (FastAPI)

1. Click **"New" → "GitHub Repo"**
2. Select the same repository again
3. Click on the new service to configure it:

**Settings → General:**
- Service Name: `api`

**Settings → Variables:**
Add these environment variables:
```
YAHOO_CLIENT_ID=your_yahoo_client_id
YAHOO_CLIENT_SECRET=your_yahoo_client_secret
YAHOO_REDIRECT_URI=https://api-production-XXXX.up.railway.app/callback
APP_SECRET_KEY=generate-a-strong-random-string-here
DEBUG=false
FRONTEND_URL=https://dashboard-production-XXXX.up.railway.app
```

**Settings → Networking:**
- Click "Generate Domain" to get a public URL
- Note this URL for the next steps (e.g., `api-production-abc123.up.railway.app`)

**Settings → Deploy:**
- Custom Start Command:
```
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

4. Link the PostgreSQL database:
   - Go to Variables
   - Click "Add Reference" → Select PostgreSQL → DATABASE_URL
   - This automatically injects the database connection string

## Step 4: Create the Dashboard Service (Streamlit)

1. Click **"New" → "GitHub Repo"**
2. Select the same repository again
3. Click on the new service to configure it:

**Settings → General:**
- Service Name: `dashboard`

**Settings → Variables:**
```
API_BASE_URL=https://api-production-XXXX.up.railway.app
APP_SECRET_KEY=same-key-as-api-service
VERIFY_SSL=true
```

**Settings → Networking:**
- Click "Generate Domain" to get a public URL
- Note this URL (e.g., `dashboard-production-xyz789.up.railway.app`)

**Settings → Deploy:**
- Custom Start Command:
```
streamlit run dashboard/main.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
```

## Step 5: Update Environment Variables

Now that you have both service URLs, go back and update:

**API Service Variables:**
- Update `FRONTEND_URL` with the actual dashboard URL
- Update `YAHOO_REDIRECT_URI` with: `https://<api-url>/callback`

**Dashboard Service Variables:**
- Update `API_BASE_URL` with the actual API URL

## Step 6: Configure Yahoo Developer Console

1. Go to https://developer.yahoo.com/apps/
2. Find your app and click to edit
3. Update the **Redirect URI** to: `https://<api-url>/callback`
   - Example: `https://api-production-abc123.up.railway.app/callback`
4. Save changes

## Step 7: Deploy

Railway auto-deploys when you push to GitHub. To manually trigger:
1. Go to each service
2. Click "Deploy" → "Redeploy"

## Verification

1. Visit `https://<api-url>/health` - should return `{"status": "healthy"}`
2. Visit `https://<dashboard-url>` - should show login page
3. Click "Login with Yahoo" and complete OAuth flow
4. You should be redirected back to the dashboard

## Environment Variables Reference

### API Service
| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection (auto from Railway) | - |
| `YAHOO_CLIENT_ID` | From Yahoo Developer Console | dj0yJm... |
| `YAHOO_CLIENT_SECRET` | From Yahoo Developer Console | abc123... |
| `YAHOO_REDIRECT_URI` | OAuth callback URL | https://api-xxx.up.railway.app/callback |
| `APP_SECRET_KEY` | Random string for sessions | use `openssl rand -hex 32` |
| `DEBUG` | Enable debug mode | false |
| `FRONTEND_URL` | Dashboard URL for redirects | https://dashboard-xxx.up.railway.app |

### Dashboard Service
| Variable | Description | Example |
|----------|-------------|---------|
| `API_BASE_URL` | FastAPI backend URL | https://api-xxx.up.railway.app |
| `APP_SECRET_KEY` | Same as API service | - |
| `VERIFY_SSL` | Verify SSL certificates | true |

## Troubleshooting

### OAuth redirect fails
- Verify `YAHOO_REDIRECT_URI` matches exactly in both Railway and Yahoo Developer Console
- Check the API service logs for errors

### Database connection fails
- Ensure PostgreSQL service is linked to the API service
- Check that `DATABASE_URL` appears in the API service variables

### Dashboard can't reach API
- Verify `API_BASE_URL` is correct (no trailing slash)
- Check API service is running and has a public domain
- Look at dashboard logs for connection errors

### View Logs
- Click on any service → "Logs" tab to see real-time logs

## Cost Estimate

Railway pricing (as of 2024):
- **Starter plan:** $5/month includes $5 usage credit
- **Typical usage for this app:** ~$10-15/month total
  - PostgreSQL: ~$5/month
  - API service: ~$3-5/month
  - Dashboard service: ~$3-5/month

## Updating the Application

Push to GitHub and Railway auto-deploys:
```bash
git add .
git commit -m "Update feature"
git push origin main
```

Railway will automatically rebuild and redeploy both services.
