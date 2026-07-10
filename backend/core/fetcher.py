"""
core/fetcher.py — QB transactions + attachments fetch [phase 1]
================================================================

Supported QBO entity types (per attachment migration plan):
  Bill, Invoice, Check, Expense, CreditCardExpense,
  JournalEntry, Deposit, CreditCardCredit, SalesReceipt,
  CreditMemo, VendorCredit

Strategy per type:
  Phase A — Fetch ALL Attachable records page by page.
             Filter by supported entity types.
             Download each file IMMEDIATELY after fetching (URIs expire ~15min).
             Build map: { entity_type → { txn_id → [att_records] } }

  Phase B — Fetch transaction details for each type separately
             using the correct QB entity name.

  Phase C — Build index.json with all transactions + attachments.

QB entity names:
  Bill, Invoice, Check, Purchase (covers Expense/CreditCardExpense/Deposit/CreditCardCredit),
  JournalEntry, SalesReceipt, CreditMemo, VendorCredit

Note on Purchase type:
  QB consolidates Expense, Check, CreditCardExpense, CreditCardCredit, Deposit
  under "Purchase" entity. We store the original AttachableRef type to preserve
  the distinction for Wafeq mapping.
"""

import time
import logging
from datetime import datetime, timezone

import requests

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import QB_BASE_URL, QB_PAGE_SIZE
from core.auth import get_access_token
from core.storage import save_index, load_index, save_attachment_file, upsert_company

log = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 2

# ── Supported QBO entity types in Attachable ──────────────────────────────────
SUPPORTED_ENTITY_TYPES = {
    "Bill",
    "Invoice",
    "Check",
    "Expense",
    "CreditCardExpense",
    "JournalEntry",
    "Deposit",
    "CreditCardCredit",
    "SalesReceipt",
    "Purchase",       # QB umbrella for Expense/Check/CC types
    "CreditMemo",     # Credit Note
    "VendorCredit",   # Debit Note
}

# QB entity type → QB SQL entity name for fetching details
QB_ENTITY_SQL = {
    "Bill":              "Bill",
    "Invoice":           "Invoice",
    "Check":             "Purchase",
    "Expense":           "Purchase",
    "CreditCardExpense": "Purchase",
    "CreditCardCredit":  "Purchase",
    "Deposit":           "Deposit",
    "JournalEntry":      "JournalEntry",
    "SalesReceipt":      "SalesReceipt",
    "Purchase":          "Purchase",
    "CreditMemo":        "CreditMemo",
    "VendorCredit":      "VendorCredit",
}

# QB entity type → date field name for WHERE clause
QB_DATE_FIELD = {
    "Bill":         "TxnDate",
    "Invoice":      "TxnDate",
    "Purchase":     "TxnDate",
    "Deposit":      "TxnDate",
    "JournalEntry": "TxnDate",
    "SalesReceipt": "TxnDate",
    "CreditMemo":   "TxnDate",
    "VendorCredit": "TxnDate",
}

# QB Purchase PaymentType → exact QBO sub-type
PURCHASE_PAYMENT_TYPE = {
    "Check":      "Check",
    "Cash":       "Expense",
    "CreditCard": "CreditCardExpense",
}


def _qb_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept":        "application/json",
    }


# ── Download file from S3 ──────────────────────────────────────────────────────

def _download_file(uri: str, file_name: str, emit, refresh_uri_fn=None) -> bytes | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            emit(f"    Downloading {file_name} (attempt {attempt})...", "info")
            resp = requests.get(uri, timeout=60)
            resp.raise_for_status()
            emit(f"    ✓ Downloaded {file_name} ({len(resp.content)//1024}KB)", "ok")
            return resp.content
        except requests.HTTPError as e:
            if resp.status_code == 401 and refresh_uri_fn and attempt < MAX_RETRIES:
                emit(f"    ↻ URL expired, fetching fresh download link...", "warn")
                new_uri = refresh_uri_fn()
                if new_uri:
                    uri = new_uri
                    continue
            emit(f"    ✕ Attempt {attempt}/{MAX_RETRIES} failed: {e}", "warn")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except requests.RequestException as e:
            emit(f"    ✕ Attempt {attempt}/{MAX_RETRIES} failed: {e}", "warn")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    emit(f"    ✕ All {MAX_RETRIES} attempts failed for {file_name}", "err")
    return None


# ── Phase A: Fetch all Attachables + download immediately ─────────────────────

def _fetch_attachables_with_download(
    access_token: str, realm_id: str,
    txn_limit: int | None, emit,
    date_from: str = None, date_to: str = None,
    entity_types: set = None,
) -> tuple[dict, dict, int, int, int]:
    """
    Fetches Attachable records page by page per type.
    QB WHERE clause supports only single type — so multiple types = multiple passes.
    Downloads each file immediately while TempDownloadUri is fresh (~15min).
    """
    allowed = entity_types or SUPPORTED_ENTITY_TYPES

    emit("═══ Phase A: Fetch + Download Attachments ═══", "info")
    emit(f"  Supported types: {', '.join(sorted(allowed))}", "info")
    if txn_limit:
        emit(f"  Limit: {txn_limit} unique transactions", "warn")
    if date_from or date_to:
        emit(f"  Date filter: {date_from or 'any'} → {date_to or 'any'}", "warn")
    emit(f"  QB page size: {QB_PAGE_SIZE} records/page", "info")

    url     = f"{QB_BASE_URL}/v3/company/{realm_id}/query"
    headers = _qb_headers(access_token)

    type_txn_map: dict[str, dict[str, list]] = {}
    flat_map:     dict[str, list]            = {}

    total_att   = 0
    dl_ok       = 0
    dl_fail     = 0
    all_unique_txns: set = set()   # across all passes, for final reporting only

    # QB Attachable WHERE clause sirf single type support karta hai
    # Multiple types ke liye alag alag passes
    if entity_types and len(entity_types) > 1:
        fetch_passes = [{t} for t in entity_types]
    else:
        fetch_passes = [entity_types]  # single type ya None (all)

    for pass_types in fetch_passes:
        pass_allowed = pass_types or allowed
        unique_txns: set = set()   # per-type limit — resets for every selected type
        start_pos    = 1
        page_num     = 0

        while True:
            page_num += 1

            # Single type → WHERE clause (fast)
            # None/multiple → full scan (Python mein filter hoga)
            if pass_types and len(pass_types) == 1:
                single_type = list(pass_types)[0]
                sql = (
                    f"SELECT * FROM Attachable "
                    f"WHERE AttachableRef.EntityRef.Type = '{single_type}' "
                    f"STARTPOSITION {start_pos} MAXRESULTS {QB_PAGE_SIZE}"
                )
            else:
                sql = (
                    f"SELECT * FROM Attachable "
                    f"STARTPOSITION {start_pos} MAXRESULTS {QB_PAGE_SIZE}"
                )

            emit(f"  [Attachable] page {page_num} (startpos={start_pos})...", "info")

            resp = requests.get(
                url, headers=headers,
                params={"query": sql, "minorversion": "65"},
                timeout=60,
            )
            resp.raise_for_status()
            page_records = resp.json().get("QueryResponse", {}).get("Attachable", [])
            emit(f"  [Attachable] page {page_num}: {len(page_records)} records", "info")

            # Page 1 mein koi matching record nahi — skip this pass
            matched_in_page = [
                a for a in page_records
                for ref in (a.get("AttachableRef") or [])
                if ref.get("EntityRef", {}).get("type", "") in pass_allowed
            ]
            if not matched_in_page and page_num == 1:
                emit(f"  No {', '.join(sorted(pass_allowed))} attachments found in QB.", "warn")
                break

            limit_reached = False
            for a in page_records:
                refs = a.get("AttachableRef", [])
                if isinstance(refs, dict):
                    refs = [refs]

                for ref in refs:
                    entity_ref  = ref.get("EntityRef", {})
                    entity_type = entity_ref.get("type", "")
                    txn_id      = entity_ref.get("value", "")

                    if entity_type not in allowed or not txn_id:
                        continue

                    temp_uri = a.get("TempDownloadUri")
                    if not temp_uri:
                        continue

                    # Limit check — per selected type, not global
                    if txn_limit and txn_id not in unique_txns and len(unique_txns) >= txn_limit:
                        emit(f"  Limit {txn_limit} reached for {entity_type} — moving to next type", "warn")
                        limit_reached = True
                        break

                    unique_txns.add(txn_id)
                    all_unique_txns.add(txn_id)
                    total_att += 1
                    file_name  = a.get("FileName") or "attachment"
                    size       = a.get("Size") or a.get("FileSize") or 0

                    emit(
                        f"  [{total_att}] {entity_type}={txn_id} | "
                        f"{file_name} ({size//1024 if size else '?'}KB)",
                        "info"
                    )

                    attachable_id = a.get("Id")

                    def _refresh_temp_uri(_attachable_id=attachable_id):
                        try:
                            r = requests.get(
                                f"{QB_BASE_URL}/v3/company/{realm_id}/attachable/{_attachable_id}",
                                headers=headers,
                                params={"minorversion": "65"},
                                timeout=30,
                            )
                            r.raise_for_status()
                            return r.json().get("Attachable", {}).get("TempDownloadUri")
                        except requests.RequestException:
                            return None

                    file_bytes = _download_file(temp_uri, file_name, emit, refresh_uri_fn=_refresh_temp_uri)

                    if file_bytes is None:
                        dl_fail   += 1
                        local_file = None
                        dl_status  = "failed"
                    else:
                        local_file = save_attachment_file(
                            realm_id, txn_id, a.get("Id"), file_name, file_bytes
                        )
                        dl_ok    += 1
                        dl_status = "success"

                    att_record = {
                        "attachable_id":   a.get("Id"),
                        "file_name":       file_name,
                        "content_type":    a.get("ContentType") or "application/octet-stream",
                        "file_size":       size,
                        "note":            a.get("Note"),
                        "temp_uri":        temp_uri,
                        "include_on_send": ref.get("IncludeOnSend", False),
                        "created_at":      (a.get("MetaData") or {}).get("CreateTime"),
                        "local_file":      local_file,
                        "download_status": dl_status,
                    }

                    type_txn_map.setdefault(entity_type, {}).setdefault(txn_id, []).append(att_record)
                    flat_map.setdefault(txn_id, []).append(att_record)

                if limit_reached:
                    break

            if limit_reached or (txn_limit and len(unique_txns) >= txn_limit):
                emit(f"  Limit {txn_limit} reached for this type — moving to next type", "warn")
                break

            if len(page_records) < QB_PAGE_SIZE:
                emit(f"  Last page reached (got {len(page_records)} < {QB_PAGE_SIZE})", "info")
                break

            start_pos += QB_PAGE_SIZE

    # Summary per type
    for etype, txns in type_txn_map.items():
        att_count = sum(len(v) for v in txns.values())
        emit(f"  {etype}: {len(txns)} transactions, {att_count} attachments", "info")

    emit(
        f"═══ Phase A complete ═══ "
        f"Transactions: {len(all_unique_txns)} | Attachments: {total_att} | "
        f"✓ Downloaded: {dl_ok} | ✕ Failed: {dl_fail}",
        "ok"
    )
    return type_txn_map, flat_map, total_att, dl_ok, dl_fail


# ── Phase B: Fetch transaction details per QB entity type ─────────────────────

def _fetch_txn_details(
    access_token: str, realm_id: str,
    entity_type: str, txn_ids: set, emit,
    date_from: str = None, date_to: str = None,
) -> dict:
    """
    Fetch QB transaction detail records for a specific entity type.
    Uses Id IN (...) WHERE clause — only fetches needed records.
    Returns { txn_id → full QB record }
    """
    sql_entity = QB_ENTITY_SQL.get(entity_type, entity_type)
    date_field = QB_DATE_FIELD.get(sql_entity, "TxnDate")

    emit(f"  Fetching {sql_entity} details for {len(txn_ids)} records...", "info")

    url       = f"{QB_BASE_URL}/v3/company/{realm_id}/query"
    headers   = _qb_headers(access_token)
    found:    dict[str, dict] = {}
    start_pos = 1
    page_num  = 0

    while len(found) < len(txn_ids):
        page_num += 1

        where_parts = []
        ids_str = ", ".join(f"'{i}'" for i in txn_ids)
        where_parts.append(f"Id IN ({ids_str})")
        if date_from:
            where_parts.append(f"{date_field} >= '{date_from}'")
        if date_to:
            where_parts.append(f"{date_field} <= '{date_to}'")
        where_clause = " WHERE " + " AND ".join(where_parts)

        sql = (
            f"SELECT * FROM {sql_entity}{where_clause} "
            f"STARTPOSITION {start_pos} MAXRESULTS {QB_PAGE_SIZE}"
        )

        resp = requests.get(
            url, headers=headers,
            params={"query": sql, "minorversion": "65"},
            timeout=60,
        )
        resp.raise_for_status()
        rows = resp.json().get("QueryResponse", {}).get(sql_entity, [])
        emit(f"  [{sql_entity}] page {page_num}: {len(rows)} records", "info")

        for r in rows:
            rid = r.get("Id")
            if rid in txn_ids:
                found[rid] = r

        if len(rows) < QB_PAGE_SIZE:
            break
        start_pos += QB_PAGE_SIZE

    missing = txn_ids - set(found.keys())
    if missing:
        emit(f"  Warning: {len(missing)} {sql_entity} record(s) not found", "warn")

    emit(f"  {sql_entity}: {len(found)} details fetched", "ok")
    return found


# ── Extract fields per QB entity type ─────────────────────────────────────────

def _extract_txn_fields(txn: dict, entity_type: str) -> dict:
    """
    Extract normalized fields from a QB transaction record.
    Different entity types use different field names.
    """
    sql_entity = QB_ENTITY_SQL.get(entity_type, entity_type)

    # Common fields
    txn_id        = txn.get("Id", "")
    doc_number    = txn.get("DocNumber", "")
    txn_date      = txn.get("TxnDate", "")
    total_amt     = txn.get("TotalAmt", 0) or txn.get("Amount", 0)
    currency      = (txn.get("CurrencyRef") or {}).get("value", "")
    created_at    = (txn.get("MetaData") or {}).get("CreateTime", "")
    updated_at    = (txn.get("MetaData") or {}).get("LastUpdatedTime", "")
    private_note  = txn.get("PrivateNote", "")
    exchange_rate = txn.get("ExchangeRate", 1)
    paid_through_account = ""

    # Contact name — differs by entity type
    if sql_entity == "Bill":
        vendor_ref   = txn.get("VendorRef", {}) or {}
        contact_id   = vendor_ref.get("value", "")
        contact_name = vendor_ref.get("name", "")

    elif sql_entity in ("Invoice", "SalesReceipt", "CreditMemo"):
        cust_ref     = txn.get("CustomerRef", {}) or {}
        contact_id   = cust_ref.get("value", "")
        contact_name = cust_ref.get("name", "")

    elif sql_entity == "VendorCredit":
        vendor_ref   = txn.get("VendorRef", {}) or {}
        contact_id   = vendor_ref.get("value", "")
        contact_name = vendor_ref.get("name", "")

    elif sql_entity == "Purchase":
        entity_ref   = txn.get("EntityRef", {}) or {}
        contact_id   = entity_ref.get("value", "")
        contact_name = entity_ref.get("name", "")
        # paid_through_account — bank/CC account used for payment
        paid_through_account = (txn.get("AccountRef") or {}).get("name", "")
        # Resolve sub-type from PaymentType
        payment_type = txn.get("PaymentType", "")
        if payment_type and entity_type == "Purchase":
            entity_type = PURCHASE_PAYMENT_TYPE.get(payment_type, entity_type)

    elif sql_entity == "Deposit":
        contact_id   = ""
        contact_name = ""

    elif sql_entity == "JournalEntry":
        lines        = txn.get("Line", [])
        first_line   = lines[0] if lines else {}
        detail       = (first_line.get("JournalEntryLineDetail") or {})
        entity_ref   = (detail.get("Entity") or {})
        contact_id   = entity_ref.get("value", "")
        contact_name = entity_ref.get("name", "")

    else:
        contact_id   = ""
        contact_name = ""

    ref_number = txn.get("DocNumber") or txn.get("PrivateNote", "")[:20] or ""

    return {
        "qb_bill_id":           txn_id,
        "qbo_type":             entity_type,
        "sync_token":           txn.get("SyncToken", ""),
        "doc_number":           doc_number,
        "ref_number":           ref_number,
        "vendor_id":            contact_id,
        "vendor_name":          contact_name,
        "txn_date":             txn_date,
        "due_date":             txn.get("DueDate", ""),
        "total_amt":            total_amt,
        "balance":              txn.get("Balance", 0),
        "currency":             currency,
        "exchange_rate":        exchange_rate,
        "private_note":         private_note,
        "created_at":           created_at,
        "updated_at":           updated_at,
        "ap_account":           (txn.get("APAccountRef") or {}).get("name", ""),
        "payment_terms":        (txn.get("SalesTermRef") or {}).get("name", ""),
        "department":           (txn.get("DepartmentRef") or {}).get("name", ""),
        "paid_through_account": paid_through_account,
        # Wafeq match fields (filled in Phase 2)
        "wafeq_bill_id":        None,
        "wafeq_type":           None,
        "match_status":         "pending",
        "match_try":            None,
        "match_note":           None,
    }


# ── Main pipeline ──────────────────────────────────────────────────────────────

def fetch_and_store(
    realm_id: str,
    progress_cb=None,
    bill_limit: int = None,
    date_from: str = None,
    date_to: str = None,
    entity_types: set = None,
) -> dict:
    """
    Full Phase 1:
      Phase A: Fetch Attachable records + download files immediately
      Phase B: Fetch transaction details per entity type
      Phase C: Build + save index.json
    """
    def emit(msg: str, t: str = "info"):
        log.info(f"[FETCH] {msg}")
        if progress_cb:
            progress_cb(msg, t)

    emit("═══ Phase 1: QB Fetch Pipeline ═══", "info")
    if bill_limit:
        emit(f"Limit: {bill_limit} transactions (stops early)", "warn")
    if date_from or date_to:
        emit(f"Date filter: {date_from or 'any'} → {date_to or 'any'}", "warn")
    emit(f"QB page size: {QB_PAGE_SIZE}", "info")

    access_token = get_access_token(realm_id)
    emit(f"QB token: OK (realm={realm_id})", "info")

    # ── Phase A ───────────────────────────────────────────────────────────────
    try:
        type_txn_map, flat_map, total_att, dl_ok, dl_fail = \
            _fetch_attachables_with_download(
                access_token, realm_id, bill_limit, emit,
                date_from=date_from, date_to=date_to,
                entity_types=entity_types,
            )
    except Exception as e:
        emit(f"Phase A failed: {e}", "err")
        raise

    if not flat_map:
        emit("No transactions with file attachments found in QuickBooks.", "warn")
        idx = {
            "realm_id":   realm_id,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "summary":    {"total_bills": 0, "total_files": 0, "downloaded": 0, "failed": 0},
            "bills":      {},
        }
        save_index(realm_id, idx)
        upsert_company(realm_id, {"stats": idx["summary"]})
        return idx

    # ── Phase B ───────────────────────────────────────────────────────────────
    emit("═══ Phase B: Fetch Transaction Details ═══", "info")
    all_details: dict[str, dict] = {}

    for entity_type, txn_map in type_txn_map.items():
        txn_ids = set(txn_map.keys())
        try:
            details = _fetch_txn_details(
                access_token, realm_id, entity_type, txn_ids, emit,
                date_from=date_from, date_to=date_to,
            )
            all_details.update(details)
        except Exception as e:
            emit(f"Phase B failed for {entity_type}: {e}", "err")

    emit(f"═══ Phase B complete ═══ {len(all_details)} records fetched", "ok")

    # ── Phase C ───────────────────────────────────────────────────────────────
    emit("═══ Phase C: Building index.json ═══", "info")

    index = {
        "realm_id":   realm_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_bills": 0,
            "total_files": total_att,
            "downloaded":  dl_ok,
            "failed":      dl_fail,
        },
        "bills": {},
    }

    for entity_type, txn_map in type_txn_map.items():
        for txn_id, atts in txn_map.items():
            raw = all_details.get(txn_id, {})
            if not raw:
                emit(f"  Warning: no details for {entity_type} {txn_id} — skipping", "warn")
                continue

            fields = _extract_txn_fields(raw, entity_type)
            emit(
                f"  Indexing: {entity_type} | "
                f"{fields['doc_number'] or txn_id} | "
                f"{fields['vendor_name'] or '?'} | "
                f"{len(atts)} file(s)",
                "info"
            )

            index["bills"][txn_id] = {
                **fields,
                "attachments": [
                    {
                        "attachable_id":   att["attachable_id"],
                        "file_name":       att["file_name"],
                        "content_type":    att["content_type"],
                        "file_size_bytes": att["file_size"],
                        "note":            att["note"],
                        "created_at":      att["created_at"],
                        "include_on_send": att["include_on_send"],
                        "local_file":      att["local_file"],
                        "download_status": att["download_status"],
                        "upload_status":   "pending",
                        "wafeq_file_id":   None,
                        "error":           None,
                    }
                    for att in atts
                ],
            }

    total_txns = len(index["bills"])
    index["summary"]["total_bills"] = total_txns
    save_index(realm_id, index)
    upsert_company(realm_id, {"stats": index["summary"]})

    emit(
        f"═══ Phase 1 complete ═══ "
        f"Transactions: {total_txns} | "
        f"Files: {total_att} | "
        f"✓ Downloaded: {dl_ok} | ✕ Failed: {dl_fail}",
        "ok"
    )
    return index


# ── Retry only failed downloads (no re-fetch from QB) ──────────────────────────

def retry_failed_downloads(realm_id: str, emit=lambda *a: None) -> dict:
    """
    Scans the existing index.json for attachments with download_status == "failed",
    fetches a fresh TempDownloadUri for each via the Attachable endpoint, and
    retries the download. Does NOT re-query QuickBooks for transaction lists —
    only targets the specific attachments that previously failed.
    """
    access_token = get_access_token(realm_id)
    headers = _qb_headers(access_token)
    idx = load_index(realm_id)
    bills = idx.get("bills", {})

    failed_items = []
    for bill_id, bill in bills.items():
        for att in bill.get("attachments", []):
            if att.get("download_status") == "failed":
                failed_items.append((bill_id, att))

    total = len(failed_items)
    emit(f"═══ Retry Failed Downloads ═══ {total} file(s) to retry", "info")

    if total == 0:
        emit("No failed downloads found — nothing to retry.", "ok")
        return idx

    fixed = 0
    still_failed = 0

    for i, (bill_id, att) in enumerate(failed_items, 1):
        attachable_id = att.get("attachable_id")
        file_name     = att.get("file_name") or "attachment"
        emit(f"  [{i}/{total}] Retrying {file_name} (bill={bill_id})...", "info")

        def _refresh_temp_uri(_attachable_id=attachable_id):
            try:
                r = requests.get(
                    f"{QB_BASE_URL}/v3/company/{realm_id}/attachable/{_attachable_id}",
                    headers=headers,
                    params={"minorversion": "65"},
                    timeout=30,
                )
                r.raise_for_status()
                return r.json().get("Attachable", {}).get("TempDownloadUri")
            except requests.RequestException:
                return None

        fresh_uri = _refresh_temp_uri()
        if not fresh_uri:
            emit(f"    ✕ Could not get fresh link for {file_name}", "err")
            still_failed += 1
            continue

        file_bytes = _download_file(fresh_uri, file_name, emit, refresh_uri_fn=_refresh_temp_uri)

        if file_bytes is None:
            still_failed += 1
            continue

        local_file = save_attachment_file(realm_id, bill_id, attachable_id, file_name, file_bytes)
        att["local_file"]      = local_file
        att["download_status"] = "success"
        fixed += 1

    save_index(realm_id, idx)
    emit(
        f"═══ Retry complete ═══ Fixed: {fixed} | Still failed: {still_failed}",
        "ok"
    )
    return idx
