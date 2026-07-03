# QBO → Wafeq · Attachment Migration (Full Project)

Complete full-stack app: Flask backend + React (Vite) frontend, already wired together.

```
qbo-wafeq-full/
├── backend/                 ← Flask API (SSE fetch/match/upload, auth, admin, reports)
│   ├── app.py
│   ├── core/                 fetcher.py, matcher.py, uploader.py, auth.py, auth_users.py, storage.py
│   ├── frontend_dist/        ← pre-built React app (already dropped in — ready to run)
│   ├── .env.example          ← copy to .env and fill in
│   └── requirements.txt
└── frontend/                 ← React source (Vite) — edit here, then rebuild
    ├── src/
    ├── frontend_dist_prebuilt/  (same build as backend/frontend_dist)
    └── package.json
```

## Quick start (fastest — use the pre-built UI)

```bash
cd backend
python -m venv venv && source venv/bin/activate      # (Windows: venv\Scripts\activate)
pip install -r requirements.txt

cp .env.example .env
# edit .env: fill QB_CLIENT_ID, QB_CLIENT_SECRET, NGROK_URL

python app.py
```
Open **http://localhost:8000** (or your ngrok URL). `frontend_dist/` is already built and wired
into Flask's static folder — no npm needed to just run it.

Default login: **admin / admin123** (change via `AUTH_USERS` in `.env`, or from Settings after login).

## Editing the frontend

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173, proxies /api → localhost:8000 (run backend separately)
```

After making changes, rebuild and re-deploy into the backend:
```bash
npm run build
rm -rf ../backend/frontend_dist
cp -r dist ../backend/frontend_dist
```

## Pages (all endpoints wired)

| Page | Purpose | Backend routes |
|---|---|---|
| Login | Session auth | `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` |
| Migrate | 3-phase pipeline (Fetch→Match→Upload) with live progress bars + unified logs | `GET /api/fetch/<realm_id>` (SSE), `GET /api/match/<realm_id>` (SSE), `GET /api/upload/<realm_id>` (SSE), `GET /api/index/<realm_id>` |
| Companies | Connect/test/delete QBO companies, manage Wafeq API keys | `GET/DELETE /api/companies`, `GET /api/qbo/auth-url`, `GET /callback`, `GET /api/qbo/test/<realm_id>`, `POST /api/wafeq/key`, `POST /api/wafeq/key/activate`, `POST /api/wafeq/key/delete`, `GET /api/wafeq/test/<realm_id>` |
| Report | Summary, type breakdown, transactions, Excel export | `GET /api/report/<realm_id>`, `GET /api/export/<realm_id>` |
| Admin | Users CRUD + audit log (admin role only) | `GET/POST /api/admin/users`, `POST /api/admin/users/<u>/reset-password`, `DELETE /api/admin/users/<u>`, `GET /api/admin/audit`, `GET /api/admin/report` |
| Settings | Password change + theme | `POST /api/auth/change-password` |

Manual match (used when auto-matching misses a record) is wired via `POST /api/manual-match`
in `frontend/src/lib/api.js` (`api.manualMatch`) — call it from a Report row if you want a
"fix match" action; not yet surfaced as a button in the UI, ready to hook up.

## Progress bars — accuracy note

- **Match** and **Upload** phases already emit `[i/total]` progress from the backend, so their
  bars fill exactly.
- **Fetch** emits status text without a running count, so its bar advances by log-line volume
  and completes at 100% on `__DONE__`. To make it exact, patch `core/fetcher.py`:

  Find (around line 550):
  ```python
      for entity_type, txn_map in type_txn_map.items():
          for txn_id, atts in txn_map.items():
              raw = all_details.get(txn_id, {})
  ```
  Replace with:
  ```python
      _idx_total = sum(len(m) for m in type_txn_map.values())
      _idx_i = 0
      for entity_type, txn_map in type_txn_map.items():
          for txn_id, atts in txn_map.items():
              _idx_i += 1
              emit(f"  Indexing [{_idx_i}/{_idx_total}]", "info")
              raw = all_details.get(txn_id, {})
  ```
  Validate: `python -c "import ast; ast.parse(open('core/fetcher.py').read())"`

## Deploying on EC2 (matches your existing setup pattern)

1. `pip install -r requirements.txt` in a venv
2. `.env` with production `QB_CLIENT_ID`/`QB_CLIENT_SECRET`/`NGROK_URL` (or your real domain)
3. `npm run build` locally → copy `dist/` to `backend/frontend_dist/` (already done in this zip)
4. Run behind Gunicorn + Nginx like your other Flask apps, e.g.:
   `gunicorn -w 2 -k gthread -b 127.0.0.1:8000 app:app`
5. Nginx reverse-proxy `/` to port 8000; SSE routes need `X-Accel-Buffering: no` (already set by
   the backend) and Nginx should NOT buffer these — add `proxy_buffering off;` for the
   `/api/fetch`, `/api/match`, `/api/upload` locations.
