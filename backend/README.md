# QBO → Wafeq Migration Tool

## Setup

### 1. Environment
```bash
copy .env.example .env
# Fill in QB_CLIENT_ID, QB_CLIENT_SECRET, NGROK_URL
```

### 2. Install Python dependencies
```bash
uv pip install -r requirements.txt
```

### 3. Install Node.js (for React frontend)
Download from nodejs.org — LTS version.

### 4. Run
```bash
# Terminal 1 — ngrok
ngrok http 8000 --request-header-add "ngrok-skip-browser-warning:true"

# Terminal 2 — app (builds React automatically on first run)
python start.py
```

### Development mode (hot reload)
```bash
# Terminal 1 — Flask
python app.py

# Terminal 2 — React dev server (proxies API to Flask)
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

## Project structure
```
qbo_wafeq/
├── .env.example        ← Copy to .env, fill credentials
├── config.py           ← Reads .env, no hardcoded secrets
├── app.py              ← Flask API routes
├── start.py            ← One command: builds React + starts Flask
├── requirements.txt
├── core/
│   ├── auth.py         ← QB token management
│   ├── fetcher.py      ← QB bills + attachments (phase 1)
│   ├── storage.py      ← Local JSON storage
│   ├── matcher.py      ← Wafeq fetch + matching (phase 2)
│   └── uploader.py     ← Upload to Wafeq (phase 3)
├── frontend/           ← React source (Vite + CSS Modules)
│   ├── src/
│   │   ├── App.jsx
│   │   ├── context/    ← Theme + App state
│   │   ├── components/ ← Badge, ProgressBar, LogPanel, Sidebar, Toast
│   │   ├── pages/      ← Dashboard (all tabs)
│   │   ├── hooks/      ← useSSE
│   │   └── utils/      ← api helpers
│   └── package.json
├── frontend_dist/      ← Built React app (auto-generated)
├── data/tokens/        ← QB OAuth tokens (gitignored)
├── downloads/          ← Downloaded attachment files (gitignored)
└── qb_profiles/        ← Legacy token location (gitignored)
```
