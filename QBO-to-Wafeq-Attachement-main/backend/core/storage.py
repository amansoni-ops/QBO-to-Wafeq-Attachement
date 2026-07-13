"""
core/storage.py — Local file and index storage
================================================
Manages:
  - companies.json  (connected companies list)
  - downloads/{realm_id}/index.json  (bill ↔ attachment mapping)
  - downloads/{realm_id}/files/  (actual attachment files)

File naming convention:
  {bill_id}___{attachable_id}___{filename}
  Triple underscore separates parts unambiguously.
"""

import json
import re
from pathlib import Path

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import DATA_DIR, TOKENS_DIR, DOWNLOADS_DIR

# Auto-create folders on import
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
Path(TOKENS_DIR).mkdir(parents=True, exist_ok=True)
Path(DOWNLOADS_DIR).mkdir(parents=True, exist_ok=True)

COMPANIES_FILE = Path(DATA_DIR) / "companies.json"


# ── Companies DB ─────────────────────────────────────────────────────────────

def load_companies() -> dict:
    if not COMPANIES_FILE.exists():
        return {}
    return json.loads(COMPANIES_FILE.read_text())

def save_companies(data: dict):
    COMPANIES_FILE.write_text(json.dumps(data, indent=2))

def upsert_company(realm_id: str, fields: dict):
    db = load_companies()
    db[realm_id] = {**db.get(realm_id, {}), **fields}
    save_companies(db)

def delete_company(realm_id: str):
    db = load_companies()
    db.pop(realm_id, None)
    save_companies(db)


# ── Per-company paths ─────────────────────────────────────────────────────────

def company_files_dir(realm_id: str) -> Path:
    d = Path(DOWNLOADS_DIR) / realm_id / "files"
    d.mkdir(parents=True, exist_ok=True)
    return d

def index_path(realm_id: str) -> Path:
    d = Path(DOWNLOADS_DIR) / realm_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "index.json"


# ── Index (bill ↔ attachment map) ─────────────────────────────────────────────

def load_index(realm_id: str) -> dict:
    p = index_path(realm_id)
    if not p.exists():
        return {
            "realm_id":   realm_id,
            "fetched_at": None,
            "summary":    {},
            "bills":      {},
        }
    return json.loads(p.read_text())

def save_index(realm_id: str, data: dict):
    index_path(realm_id).write_text(json.dumps(data, indent=2))


def clear_index(realm_id: str):
    """Delete index.json AND downloaded attachment files for a realm —
    used before every fresh fetch so old data never lingers alongside new."""
    p = index_path(realm_id)
    if p.exists():
        p.unlink()
    files_dir = company_files_dir(realm_id)
    if files_dir.exists():
        for f in files_dir.iterdir():
            if f.is_file():
                f.unlink()


# ── File naming ───────────────────────────────────────────────────────────────

def _sanitize(s: str) -> str:
    return re.sub(r"[^\w.\-]", "_", str(s or "unknown"))

def safe_filename(bill_id: str, attachable_id: str, original_name: str) -> str:
    """
    Format: {bill_id}___{attachable_id}___{sanitized_name}
    Example: 456___789___invoice_scan.pdf
    """
    return f"{_sanitize(bill_id)}___{_sanitize(attachable_id)}___{_sanitize(original_name)}"


# ── Save attachment file ──────────────────────────────────────────────────────

def save_attachment_file(
    realm_id: str,
    bill_id: str,
    attachable_id: str,
    file_name: str,
    file_bytes: bytes,
) -> str:
    """Saves file to downloads/{realm_id}/files/, returns local filename."""
    local_name = safe_filename(bill_id, attachable_id, file_name)
    dest       = company_files_dir(realm_id) / local_name
    dest.write_bytes(file_bytes)
    return local_name


# ── Stats helper ──────────────────────────────────────────────────────────────

def get_stats(realm_id: str) -> dict:
    idx         = load_index(realm_id)
    bills       = idx.get("bills", {})
    total_bills = len(bills)
    total_files = sum(len(b.get("attachments", [])) for b in bills.values())
    downloaded  = sum(
        1 for b in bills.values()
        for a in b.get("attachments", [])
        if a.get("download_status") == "success"
    )
    matched = sum(1 for b in bills.values() if b.get("wafeq_bill_id"))
    uploaded = sum(
        1 for b in bills.values()
        for a in b.get("attachments", [])
        if a.get("upload_status") == "success"
    )
    return {
        "total_bills":  total_bills,
        "total_files":  total_files,
        "downloaded":   downloaded,
        "matched":      matched,
        "uploaded":     uploaded,
        "fetched_at":   idx.get("fetched_at"),
    }
