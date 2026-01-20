# Local Development Guide

This guide explains how to set up and run the Yahoo Fantasy Dashboard locally.

## Prerequisites

- Python 3.10 or higher
- Git
- A Yahoo Developer account with an app configured (for OAuth)

## Initial Setup (One-Time)

### 1. Clone the Repository
```bash
git clone <repository-url>
cd yahoo-nba-fantasy-dashboard
```

### 2. Create Virtual Environment
```bash
python -m venv venv
```

### 3. Activate Virtual Environment
```bash
# Windows (Command Prompt)
venv\Scripts\activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Windows (Git Bash)
source venv/Scripts/activate

# macOS/Linux
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -e .
```

This installs the project in "editable" mode, allowing imports between packages (`app`, `backend`, `dashboard`).

### 5. Configure Environment Variables
```bash
# Copy the example file
cp .env.example .env

# Edit .env with your values (see below)
```

### 6. Generate SSL Certificate (Required for Yahoo OAuth)
Yahoo requires HTTPS even for localhost. Generate a self-signed certificate:

```bash
# Windows (Git Bash) - note the double slashes
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes -subj "//CN=localhost"

# macOS/Linux
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes -subj "/CN=localhost"
```

### 7. Configure Yahoo Developer App
1. Go to https://developer.yahoo.com/apps/
2. Create or edit your app
3. Set the Redirect URI to: `https://localhost:8080/callback`
4. Copy your Client ID and Client Secret to `.env`

## Environment Variables

Edit `.env` with your values:

```bash
# Required - from Yahoo Developer Console
YAHOO_CLIENT_ID=your_client_id_here
YAHOO_CLIENT_SECRET=your_client_secret_here
YAHOO_REDIRECT_URI=https://localhost:8080/callback

# Required - generate a random key for production
APP_SECRET_KEY=dev-secret-change-in-production

# Optional - defaults shown
DEBUG=true
FRONTEND_URL=http://localhost:8501
API_BASE_URL=https://localhost:8080
VERIFY_SSL=false
DATABASE_URL=sqlite:///./data/fantasy.db
```

## Running the Application

You need **two terminals** - one for the backend, one for the frontend.

### Terminal 1: FastAPI Backend
```bash
cd C:\Users\darch\Projects\yahoo-nba-fantasy-dashboard
venv\Scripts\activate
uvicorn backend.main:app --host localhost --port 8080 --ssl-keyfile key.pem --ssl-certfile cert.pem --reload
```

The `--reload` flag enables auto-reload when you change code.

**Expected output:**
```
INFO:     Uvicorn running on https://localhost:8080 (Press CTRL+C to quit)
INFO:     Started reloader process
```

### Terminal 2: Streamlit Dashboard
```bash
cd C:\Users\darch\Projects\yahoo-nba-fantasy-dashboard
venv\Scripts\activate
streamlit run dashboard/app.py --server.port 8501
```

**Expected output:**
```
You can now view your Streamlit app in your browser.
Local URL: http://localhost:8501
```

## Accessing the Application

1. Open http://localhost:8501 in your browser
2. Click "Login with Yahoo"
3. Accept the SSL certificate warning (click Advanced → Proceed)
4. Authorize on Yahoo
5. You'll be redirected back to the dashboard

## Troubleshooting

### SSL Certificate Warning
When first accessing `https://localhost:8080`, your browser will warn about the self-signed certificate. This is expected for local development:
- **Chrome**: Click "Advanced" → "Proceed to localhost (unsafe)"
- **Firefox**: Click "Advanced" → "Accept the Risk and Continue"

### "Module not found" Errors
Make sure you ran `pip install -e .` to install the project in editable mode.

### "Connection refused" Errors
Ensure both servers (FastAPI and Streamlit) are running in separate terminals.

### OAuth Errors
- Verify `YAHOO_REDIRECT_URI` in `.env` exactly matches what's in Yahoo Developer Console
- Make sure you're using `https://` (not `http://`) for the redirect URI
- Check that port 8080 matches in both places

### Database Issues
The SQLite database is created automatically at `data/fantasy.db`. To reset:
```bash
rm data/fantasy.db
# Restart FastAPI - tables will be recreated
```

## Development Tips

### API Documentation
FastAPI auto-generates API docs at:
- Swagger UI: https://localhost:8080/docs
- ReDoc: https://localhost:8080/redoc

### Checking Logs
- FastAPI logs appear in Terminal 1
- Streamlit logs appear in Terminal 2

### Database Inspection
You can inspect the SQLite database with any SQLite browser, or via Python:
```python
import sqlite3
conn = sqlite3.connect('data/fantasy.db')
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
print([row[0] for row in cursor])
```

## Stopping the Application

Press `Ctrl+C` in each terminal to stop the servers.
