"""
core/uploader.py — Upload attachments to Wafeq [phase 3]
=========================================================

Confirmed flow (from Ziad + Jupyter test):

  Step 1: POST /v1/files/
          multipart: file=<binary>
          Response: { "id": "att_xxx", ... }

  Step 2: GET /v1/{endpoint}/{wafeq_id}/
          Read existing "attachments" list on the record

  Step 3: PATCH /v1/{endpoint}/{wafeq_id}/
          Body: { "attachments": ["att_existing", "att_new"] }

Wafeq endpoint per type:
  bill     → /v1/bills/{id}/
  invoice  → /v1/invoices/{id}/
  journal  → /v1/journal-entries/{id}/

Field name: "attachments" (plural, confirmed from Jupyter test)
Method:     PATCH (confirmed)
"""

import logging
import time
from pathlib import Path

import requests

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import WAFEQ_BASE_URL, DOWNLOADS_DIR
from core.storage import load_index, save_index, upsert_company

log = logging.getLogger(__name__)

ATTACH_FIELD = "attachments"           # confirmed from Jupyter test
UPLOAD_URL   = f"{WAFEQ_BASE_URL}/files/"

# Wafeq endpoint per type — used in Step 2 + Step 3
WAFEQ_ENDPOINTS = {
    "bill":        "bills",
    "invoice":     "invoices",
    "journal":     "manual-journals",
    "credit-note": "credit-notes",
    "debit-note":  "debit-notes",
    "expense":     "expenses",
}

MAX_RETRIES = 3
RETRY_DELAY = 2


def _auth(api_key: str) -> dict:
    return {"Authorization": f"Api-Key {api_key}"}


def _json_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


def _wafeq_endpoint(wafeq_type: str) -> str:
    """Return the correct Wafeq REST endpoint segment for a given type."""
    return WAFEQ_ENDPOINTS.get(str(wafeq_type or "bill").lower(), "bills")


# ── Step 1: POST /v1/files/ → att_id ─────────────────────────────────────────

def _upload_file(api_key: str, file_path: Path, file_name: str, content_type: str, emit) -> str:
    """Upload file to Wafeq Files API. Returns att_id."""
    emit(f"  [Step 1] POST {UPLOAD_URL}", "info")
    emit(f"  [Step 1] file={file_name} size={file_path.stat().st_size//1024}KB", "info")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with open(file_path, "rb") as f:
                resp = requests.post(
                    UPLOAD_URL,
                    headers=_auth(api_key),
                    files={"file": (file_name, f, content_type)},
                    timeout=60,
                )
            emit(f"  [Step 1] HTTP {resp.status_code} (attempt {attempt})", "info")
            if resp.status_code == 401:
                raise RuntimeError("401 Unauthorized — check Wafeq API key")
            if not resp.ok:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")

            data   = resp.json()
            emit(f"  [Step 1] Response: {data}", "info")
            att_id = data.get("id")
            if not att_id:
                raise RuntimeError(f"No 'id' in response: {data}")
            emit(f"  [Step 1] ✓ att_id={att_id}", "ok")
            return str(att_id)

        except RuntimeError:
            raise
        except Exception as e:
            emit(f"  [Step 1] attempt {attempt} error: {e}", "warn")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                raise RuntimeError(f"Upload failed after {MAX_RETRIES} attempts: {e}")


# ── Step 2: GET record → existing attachments ─────────────────────────────────

def _get_existing_attachments(api_key: str, wafeq_id: str, wafeq_type: str, emit) -> list:
    """
    GET /v1/{endpoint}/{wafeq_id}/
    Returns list of existing attachment IDs already on the record.
    """
    endpoint = _wafeq_endpoint(wafeq_type)
    url      = f"{WAFEQ_BASE_URL}/{endpoint}/{wafeq_id}/"
    emit(f"  [Step 2] GET {url}", "info")

    resp = requests.get(url, headers=_json_headers(api_key), timeout=15)
    emit(f"  [Step 2] HTTP {resp.status_code}", "info")

    if resp.status_code == 401: raise RuntimeError("401 Unauthorized")
    if resp.status_code == 404: raise RuntimeError(f"{wafeq_type} {wafeq_id} not found in Wafeq")
    resp.raise_for_status()

    data = resp.json()
    raw  = data.get(ATTACH_FIELD, []) or []
    emit(f"  [Step 2] Current '{ATTACH_FIELD}': {raw}", "info")

    ids = []
    if isinstance(raw, str) and raw:
        ids = [raw]
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item:
                ids.append(item)
            elif isinstance(item, dict):
                fid = item.get("id") or item.get("uuid")
                if fid:
                    ids.append(str(fid))

    emit(f"  [Step 2] Existing IDs ({len(ids)}): {ids}", "info")
    return ids


# ── Step 3: PATCH record with merged attachments ──────────────────────────────

def _patch_record(api_key: str, wafeq_id: str, wafeq_type: str, att_ids: list, emit) -> dict:
    """
    PATCH /v1/{endpoint}/{wafeq_id}/
    Body: { "attachments": ["att_existing", ..., "att_new"] }
    """
    endpoint = _wafeq_endpoint(wafeq_type)
    url      = f"{WAFEQ_BASE_URL}/{endpoint}/{wafeq_id}/"
    body     = {ATTACH_FIELD: att_ids}

    emit(f"  [Step 3] PATCH {url}", "info")
    emit(f"  [Step 3] Body: {body}", "info")

    resp = requests.patch(
        url, headers=_json_headers(api_key), json=body, timeout=30,
    )
    emit(f"  [Step 3] HTTP {resp.status_code}", "info")

    if resp.status_code == 401: raise RuntimeError("401 Unauthorized")
    if resp.status_code == 404: raise RuntimeError(f"{wafeq_type} {wafeq_id} not found")
    if resp.status_code == 400:
        emit(f"  [Step 3] 400 response: {resp.text}", "err")
        raise RuntimeError(f"400 Bad Request: {resp.text[:300]}")
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    result      = resp.json() if resp.content else {}
    returned    = result.get(ATTACH_FIELD, "(not in response)")
    emit(f"  [Step 3] Response '{ATTACH_FIELD}': {returned}", "info")
    emit(f"  [Step 3] ✓ Record patched successfully", "ok")
    return result


# ── Main upload pipeline ───────────────────────────────────────────────────────

def run_upload(realm_id: str, api_key: str, progress_cb=None, retry_failed: bool = False, single_bill_id: str = None) -> dict:
    """
    Phase 3 — upload + link for ALL transaction types.

    single_bill_id: if set, only process that one bill (single bill retry from UI).

    For each matched transaction (bill/invoice/journal):
      Step 1: POST /v1/files/                    → att_id
      Step 2: GET  /v1/{endpoint}/{wafeq_id}/    → existing attachments
      Step 3: PATCH /v1/{endpoint}/{wafeq_id}/   → merged list

    Automatically uses the correct Wafeq endpoint based on wafeq_type field.
    """
    def emit(msg: str, t: str = "info"):
        log.info(f"[UPLOAD] {msg}")
        if progress_cb:
            progress_cb(msg, t)

    idx = load_index(realm_id)
    if not idx.get("bills"):
        emit("No transactions in index — run Phase 1 first.", "warn")
        return {}

    files_dir = Path(DOWNLOADS_DIR) / realm_id / "files"

    # Count eligible files
    total_files = 0
    for txn in idx["bills"].values():
        if txn.get("match_status") != "matched": continue
        for att in txn.get("attachments", []):
            if att.get("upload_status") == "success": continue
            if retry_failed and att.get("upload_status") != "failed": continue
            if not retry_failed and att.get("upload_status") == "failed": continue
            if att.get("download_status") == "success": total_files += 1

    mode = "RETRY FAILED" if retry_failed else "UPLOAD PENDING"
    if single_bill_id:
        mode = f"SINGLE BILL: {single_bill_id}"
    emit(f"═══ Phase 3: {mode} ═══", "info")
    emit(f"Upload URL:    POST {UPLOAD_URL}", "info")
    emit(f"Attach field:  '{ATTACH_FIELD}' (confirmed)", "info")
    emit(f"Eligible files: {total_files}", "info")

    if total_files == 0:
        emit("Nothing to upload — all files already processed.", "warn")
        return {"uploaded": 0, "failed": 0, "skipped": 0}

    uploaded  = 0
    failed    = 0
    skipped   = 0
    current   = 0
    bill_num  = 0
    # Count matched bills for per-bill progress display
    matched_bills = [
        tid for tid, t in idx["bills"].items()
        if t.get("match_status") == "matched"
        and (not single_bill_id or tid == single_bill_id)
    ]
    bill_total = len(matched_bills)

    for txn_id, txn in idx["bills"].items():
        # Single bill mode — skip all other bills
        if single_bill_id and txn_id != single_bill_id:
            continue

        if txn.get("match_status") != "matched":
            for att in txn.get("attachments", []):
                if att.get("upload_status") not in ("success",):
                    att["upload_status"] = "skipped"
                    skipped += 1
            continue

        wafeq_id   = txn["wafeq_bill_id"]
        wafeq_type = txn.get("wafeq_type") or "bill"
        qbo_type   = txn.get("qbo_type", "Bill")
        atts       = txn.get("attachments", [])
        endpoint   = _wafeq_endpoint(wafeq_type)

        bill_num += 1
        emit(
            f"── Bill {bill_num}/{bill_total}: {qbo_type} {txn.get('doc_number', txn_id)} "
            f"→ Wafeq {wafeq_type} {wafeq_id} "
            f"({len(atts)} attachment(s)) "
            f"[PATCH /{endpoint}/]",
            "info"
        )

        for att in atts:
            status = att.get("upload_status")

            if status == "success":
                emit(f"  Skip (already done): {att['file_name']}", "info")
                skipped += 1; continue
            if not retry_failed and status == "failed":
                skipped += 1; continue
            if retry_failed and status != "failed":
                skipped += 1; continue
            if att.get("download_status") != "success" or not att.get("local_file"):
                att["upload_status"] = "skipped"
                att["error"]         = "File not downloaded from QBO"
                emit(f"  Skip (not downloaded): {att['file_name']}", "warn")
                skipped += 1; continue

            current   += 1
            file_path  = files_dir / att["local_file"]
            ct         = att.get("content_type", "application/octet-stream")
            fname      = att["file_name"]
            size_kb    = (att.get("file_size_bytes") or 0) // 1024

            emit(f"  [{current}/{total_files}] {fname} ({size_kb}KB)", "info")

            if not file_path.exists():
                att["upload_status"] = "failed"
                att["error"]         = f"Local file missing: {att['local_file']}"
                emit(f"  ✕ File not found: {file_path}", "err")
                failed += 1
                save_index(realm_id, idx)
                continue

            # ── Step 1 ────────────────────────────────────────────────────────
            try:
                att_id = _upload_file(api_key, file_path, fname, ct, emit)
            except Exception as e:
                att["upload_status"] = "failed"
                att["error"]         = f"Step 1 (upload) failed: {e}"
                emit(f"  ✕ Step 1 FAILED: {e}", "err")
                failed += 1
                save_index(realm_id, idx)
                continue

            # ── Step 2 ────────────────────────────────────────────────────────
            try:
                existing = _get_existing_attachments(api_key, wafeq_id, wafeq_type, emit)
            except Exception as e:
                att["upload_status"] = "failed"
                att["wafeq_file_id"] = att_id
                att["error"]         = f"Step 2 (GET record) failed: {e}"
                emit(f"  ✕ Step 2 FAILED: {e}", "err")
                failed += 1
                save_index(realm_id, idx)
                continue

            # ── Step 3 ────────────────────────────────────────────────────────
            try:
                merged = existing + [att_id] if att_id not in existing else existing
                _patch_record(api_key, wafeq_id, wafeq_type, merged, emit)

                att["upload_status"] = "success"
                att["wafeq_file_id"] = att_id
                att["error"]         = None
                emit(f"  ✓ {fname} → linked to {wafeq_type} {wafeq_id}", "ok")
                uploaded += 1

            except Exception as e:
                att["upload_status"] = "failed"
                att["wafeq_file_id"] = att_id
                att["error"]         = f"Step 3 (PATCH) failed: {e}"
                emit(f"  ✕ Step 3 FAILED: {e}", "err")
                emit(f"  File uploaded (att_id={att_id}) but NOT linked", "warn")
                failed += 1

            save_index(realm_id, idx)

    save_index(realm_id, idx)
    failed_total = sum(
        1 for t in idx["bills"].values()
        for a in t.get("attachments", [])
        if a.get("upload_status") == "failed"
    )
    upsert_company(realm_id, {
        "stats": {
            **idx.get("summary", {}),
            "uploaded": uploaded,
            "failed":   failed_total,
        }
    })

    emit(
        f"═══ Upload complete ═══ "
        f"✓ Linked: {uploaded} | ✕ Failed: {failed} | — Skipped: {skipped}",
        "ok"
    )
    return {"uploaded": uploaded, "failed": failed, "skipped": skipped}
