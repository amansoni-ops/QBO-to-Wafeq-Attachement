# QBO → Wafeq · Attachment Migration UI (React + Vite)

Full React frontend for the QBO→Wafeq attachment migration backend.
Sidebar navigation with 5 pages, per-phase progress bars, and unified live logs.

## Pages
| Page | What it does | Endpoints used |
|---|---|---|
| **Migrate** | 3-phase pipeline (Fetch → Match → Upload) with live progress bars + unified logs | `/api/fetch`, `/api/match`, `/api/upload`, `/api/index` |
| **Companies** | Connect/test/delete QBO companies · manage Wafeq API keys | `/api/companies`, `/api/qbo/auth-url`, `/api/qbo/test`, `/api/wafeq/key(*)` |
| **Report** | Summary, type breakdown, transactions, Excel export | `/api/report`, `/api/export` |
| **Admin** | Users CRUD + audit log (admin role only) | `/api/admin/users`, `/api/admin/audit` |
| **Settings** | Password change + theme | `/api/auth/change-password` |
| **Login** | Session auth guard | `/api/auth/login`, `/api/auth/me`, `/api/auth/logout` |

## Dev
```bash
npm install
npm run dev          # http://localhost:5173  (proxies /api → localhost:8000)
```
Vite proxies `/api` and `/callback` to the Flask backend on port 8000 (see `vite.config.js`).
Run the Flask backend separately: `python app.py`.

## Production build → serve from Flask
Flask serves `static_folder="frontend_dist"`. Build and copy:
```bash
npm run build
# copy dist/* into the backend's frontend_dist/
rm -rf ../backend_only/frontend_dist && cp -r dist ../backend_only/frontend_dist
```
Then open `http://localhost:8000` (or your ngrok URL). Same-origin, no proxy needed.

## Progress bars
- **Phase 2 (Match)** and **Phase 3 (Upload)** already emit `[i/total]` / `Bill x/y`, so their
  progress bars fill accurately from the backend.
- **Phase 1 (Fetch)** currently emits mostly status lines. The bar advances by log-line count and
  jumps to 100% on completion. To make it exact, apply the optional patch below.

### Optional backend patch — accurate Phase 1 progress
In `core/fetcher.py`, the index-building loop around **line 550**:

**Find:**
```python
    for entity_type, txn_map in type_txn_map.items():
        for txn_id, atts in txn_map.items():
            raw = all_details.get(txn_id, {})
```
**Replace with:**
```python
    _idx_total = sum(len(m) for m in type_txn_map.values())
    _idx_i = 0
    for entity_type, txn_map in type_txn_map.items():
        for txn_id, atts in txn_map.items():
            _idx_i += 1
            emit(f"  Indexing [{_idx_i}/{_idx_total}]", "info")
            raw = all_details.get(txn_id, {})
```
Validate before deploy: `python -c "import ast; ast.parse(open('core/fetcher.py').read())"`

## Notes
- Auth is session-cookie based (`credentials: 'include'` everywhere).
- The QBO connect flow opens a popup; the backend `_callback_page` posts a `QB_AUTH_SUCCESS`
  message which the Companies page listens for.
- Mode-based theming: the whole shell tints to the active phase color (indigo/orange/green)
  while a phase runs.
- Logs persist across page switches (kept in the shared store), so you can leave Migrate,
  check the Report, and come back without losing the stream.
