"""
core/cleanup.py — Data retention / auto-purge
==============================================
Deletes downloaded attachment files + index.json for a company once its
last fetch (`fetched_at`) is older than RETENTION_DAYS. Data is always
re-fetchable from QBO/Wafeq, so this is safe — it only clears local disk.

Does NOT touch: companies.json (connection + Wafeq key config), QB tokens,
users/audit log, app.log.
"""

import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import DOWNLOADS_DIR
from core.storage import load_index, load_companies

log = logging.getLogger(__name__)

RETENTION_DAYS = 7


def _parse_ts(ts: str):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def purge_old_data(retention_days: int = RETENTION_DAYS, emit=None) -> dict:
    """
    Scans every realm folder under downloads/, deletes files/ + index.json
    if fetched_at is older than retention_days. Returns a summary dict.
    """
    def log_msg(msg):
        log.info(f"[CLEANUP] {msg}")
        if emit:
            emit(msg)

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    root = Path(DOWNLOADS_DIR)
    purged, skipped, kept = [], [], []

    if not root.exists():
        log_msg("No downloads/ directory found — nothing to purge.")
        return {"purged": [], "skipped": [], "kept": [], "cutoff": cutoff.isoformat()}

    known_realms = set(load_companies().keys())

    for realm_dir in root.iterdir():
        if not realm_dir.is_dir():
            continue
        realm_id = realm_dir.name
        idx = load_index(realm_id)
        fetched_at = _parse_ts(idx.get("fetched_at"))

        if fetched_at is None:
            # No valid timestamp — fall back to folder mtime
            try:
                fetched_at = datetime.fromtimestamp(realm_dir.stat().st_mtime, tz=timezone.utc)
            except Exception:
                skipped.append(realm_id)
                log_msg(f"  {realm_id}: could not determine age — skipped")
                continue

        age_days = (datetime.now(timezone.utc) - fetched_at).days

        if fetched_at < cutoff:
            try:
                shutil.rmtree(realm_dir)
                purged.append(realm_id)
                log_msg(f"  {realm_id}: purged (last fetch {age_days}d ago)")
            except Exception as e:
                skipped.append(realm_id)
                log_msg(f"  {realm_id}: purge failed — {e}")
        else:
            kept.append(realm_id)
            log_msg(f"  {realm_id}: kept (last fetch {age_days}d ago, retention={retention_days}d)")

    log_msg(f"Done. Purged={len(purged)} Kept={len(kept)} Skipped={len(skipped)}")
    return {
        "purged": purged,
        "kept": kept,
        "skipped": skipped,
        "cutoff": cutoff.isoformat(),
        "retention_days": retention_days,
    }


def start_daily_cleanup_thread(retention_days: int = RETENTION_DAYS, interval_hours: int = 24):
    """Call once at app startup — runs purge_old_data() once now, then every interval_hours."""
    import threading
    import time

    def loop():
        while True:
            try:
                purge_old_data(retention_days)
            except Exception as e:
                log.error(f"[CLEANUP] scheduled run failed: {e}")
            time.sleep(interval_hours * 3600)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    log.info(f"[CLEANUP] daily auto-purge thread started (retention={retention_days}d, every {interval_hours}h)")