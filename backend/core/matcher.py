"""
core/matcher.py — Wafeq fetch + QB↔Wafeq matching  [phase 2]
=============================================================

QBO → Wafeq type mapping:
  Bill                → Bill          (/v1/bills/)
  Invoice             → Invoice       (/v1/invoices/)
  CreditMemo          → Credit Note   (/v1/credit-notes/)
  VendorCredit        → Debit Note    (/v1/debit-notes/)
  Check/Expense/CC    → Expense       (/v1/expenses/)   OR Journal (user choice)
  JournalEntry        → Manual Journal(/v1/manual-journals/)
  Deposit/CCCredit/SalesReceipt → Manual Journal

Matching priority (4-try):
  Try 1: external_id == QBO txn ID    (primary — most reliable)
  Try 2: doc/ref number + contact     (fallback)
  Try 3: doc/ref number only          (relaxed fallback)
  Try 4: amount + date / contact+date (last resort)
"""

import logging
import re

import requests

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import WAFEQ_BASE_URL, WAFEQ_PAGE_SIZE
from core.storage import load_index, save_index, upsert_company

log = logging.getLogger(__name__)


# ── QBO type → Wafeq type mapping ─────────────────────────────────────────────
QBO_TO_WAFEQ_TYPE = {
    "bill":               "bill",
    "invoice":            "invoice",
    "check":              "expense",      # default — overridden by expense_target
    "expense":            "expense",
    "creditcardexpense":  "expense",
    "journalentry":       "journal",
    "deposit":            "journal",
    "creditcardcredit":   "journal",
    "salesreceipt":       "journal",
    "creditmemo":         "credit-note",
    "vendorcredit":       "debit-note",
}

# Wafeq type → REST endpoint segment
WAFEQ_ENDPOINT_MAP = {
    "bill":        "bills",
    "invoice":     "invoices",
    "journal":     "manual-journals",
    "credit-note": "credit-notes",
    "debit-note":  "debit-notes",
    "expense":     "expenses",
}


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Api-Key {api_key}",
        "Accept":        "application/json",
        "Content-Type":  "application/json",
    }


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").lower().strip())

def _date_norm(s) -> str:
    s = str(s or "").strip()
    return s[:10] if s else ""

def _amount_norm(v) -> str:
    try:
        return f"{float(v):.2f}"
    except Exception:
        return ""


# ── Paginated Wafeq fetch ──────────────────────────────────────────────────────

def _fetch_wafeq_records(api_key: str, endpoint: str, emit=None) -> list:
    url      = f"{WAFEQ_BASE_URL}/{endpoint}/"
    all_recs = []
    offset   = 0
    page     = 0

    while True:
        page += 1
        resp = requests.get(
            url,
            headers=_headers(api_key),
            params={"limit": WAFEQ_PAGE_SIZE, "offset": offset},
            timeout=30,
        )
        if resp.status_code == 401:
            raise RuntimeError("Invalid Wafeq API key.")
        if resp.status_code == 404:
            if emit:
                emit(f"  [{endpoint}] endpoint not found — skipping", "warn")
            return []
        resp.raise_for_status()

        data    = resp.json()
        results = data.get("results", [])
        total   = data.get("count", 0)
        all_recs.extend(results)

        if emit:
            emit(
                f"  [{endpoint}] page {page}: {len(results)} records "
                f"(fetched: {len(all_recs)}/{total})",
                "info"
            )

        if not results:
            break
        if total > 0 and len(all_recs) >= total:
            break
        if not data.get("next"):
            break
        offset += WAFEQ_PAGE_SIZE

    return all_recs


# ── Field getters ──────────────────────────────────────────────────────────────

def _get_contact_name(rec: dict) -> str:
    contact = rec.get("contact")
    if isinstance(contact, dict):
        return contact.get("name", "") or contact.get("display_name", "")
    return str(contact or "")

def _get_doc_number(rec: dict, wafeq_type: str) -> str:
    if wafeq_type == "bill":
        return str(rec.get("bill_number") or "").strip()
    if wafeq_type == "invoice":
        return str(rec.get("invoice_number") or rec.get("number") or "").strip()
    if wafeq_type == "credit-note":
        return str(rec.get("credit_note_number") or rec.get("number") or "").strip()
    if wafeq_type == "debit-note":
        return str(rec.get("debit_note_number") or rec.get("number") or "").strip()
    if wafeq_type == "expense":
        return str(rec.get("reference") or rec.get("number") or "").strip()
    # journal
    return str(rec.get("reference") or rec.get("number") or "").strip()

def _get_date(rec: dict, wafeq_type: str) -> str:
    if wafeq_type == "bill":
        return _date_norm(rec.get("bill_date", ""))
    if wafeq_type == "invoice":
        return _date_norm(rec.get("invoice_date") or rec.get("date", ""))
    if wafeq_type == "credit-note":
        return _date_norm(rec.get("credit_note_date") or rec.get("date", ""))
    if wafeq_type == "debit-note":
        return _date_norm(rec.get("debit_note_date") or rec.get("date", ""))
    if wafeq_type == "expense":
        return _date_norm(rec.get("date") or "")
    return _date_norm(rec.get("date") or rec.get("journal_date", ""))

def _get_amount(rec: dict) -> str:
    return _amount_norm(
        rec.get("total_amount") or rec.get("amount") or
        rec.get("total") or rec.get("net_amount") or 0
    )


def _build_maps(records: list, wafeq_type: str) -> dict:
    external_id_map  = {}
    docnum_map       = {}
    contact_date_map = {}
    amount_date_map  = {}

    for rec in records:
        eid = str(rec.get("external_id") or "").strip()
        if eid:
            external_id_map[eid] = rec

        dn = _get_doc_number(rec, wafeq_type)
        if dn:
            docnum_map.setdefault(dn, []).append(rec)

        # reference field bhi index karo (extra matching)
        ref = str(rec.get("reference") or "").strip()
        if ref and ref != dn:
            docnum_map.setdefault(ref, []).append(rec)

        contact = _norm(_get_contact_name(rec))
        date    = _get_date(rec, wafeq_type)
        amount  = _get_amount(rec)

        if contact and date:
            contact_date_map.setdefault(f"{contact}||{date}", []).append(rec)
        if amount and date:
            amount_date_map.setdefault(f"{amount}||{date}", []).append(rec)

    return {
        "external_id":  external_id_map,
        "docnum":       docnum_map,
        "contact_date": contact_date_map,
        "amount_date":  amount_date_map,
    }


def _rec_summary(rec: dict, wafeq_type: str) -> dict:
    return {
        "wafeq_id":    rec.get("id"),
        "wafeq_type":  wafeq_type,
        "external_id": rec.get("external_id"),
        "doc_number":  _get_doc_number(rec, wafeq_type),
        "date":        _get_date(rec, wafeq_type),
        "amount":      _get_amount(rec),
        "contact":     _get_contact_name(rec),
        "status":      rec.get("status"),
    }


# ── Per-record matching ────────────────────────────────────────────────────────

def _match_record(qb_txn_id, doc_number, contact, txn_date, amount,
                  maps, wafeq_type, emit) -> tuple:

    # Try 1: external_id
    if qb_txn_id and qb_txn_id in maps["external_id"]:
        return "matched", maps["external_id"][qb_txn_id], 1, "external_id match"

    # Try 2: doc number + contact
    if doc_number:
        hits = maps["docnum"].get(doc_number, [])
        if hits and contact:
            contact_hits = [
                h for h in hits
                if _norm(_get_contact_name(h)) == _norm(contact)
            ]
            if len(contact_hits) == 1:
                return "matched", contact_hits[0], 2, "doc_number + contact match"
            if len(contact_hits) > 1:
                return "duplicate", contact_hits, 2, "doc_number + contact duplicated"

        # Try 3: doc number only
        if len(hits) == 1:
            return "matched", hits[0], 3, "doc_number match"
        if len(hits) > 1:
            return "duplicate", hits, 3, "doc_number duplicated"

    # Try 4a: contact + date
    if contact and txn_date:
        key  = f"{_norm(contact)}||{txn_date}"
        hits = maps["contact_date"].get(key, [])
        if len(hits) == 1:
            return "matched", hits[0], 4, "contact + date match"
        if len(hits) > 1:
            return "duplicate", hits, 4, "contact + date duplicated"

    # Try 4b: amount + date
    if amount and txn_date:
        key  = f"{amount}||{txn_date}"
        hits = maps["amount_date"].get(key, [])
        if len(hits) == 1:
            return "matched", hits[0], 4, "amount + date match"
        if len(hits) > 1:
            return "duplicate", hits, 4, "amount + date duplicated"

    return "no_match", None, 5, "no match found"


# ── Main matching pipeline ─────────────────────────────────────────────────────

def run_matching(realm_id: str, api_key: str, progress_cb=None, expense_target: str = "expense") -> dict:
    """
    Phase 2 — matching for all QBO transaction types.

    expense_target: "expense" → Check/Expense/CC → /v1/expenses/
                    "journal"  → Check/Expense/CC → /v1/manual-journals/
    """
    def emit(msg, t="info"):
        log.info(f"[MATCH] {msg}")
        if progress_cb:
            progress_cb(msg, t)

    idx = load_index(realm_id)
    if not idx.get("bills"):
        emit("No QB transactions in index. Run Phase 1 (Fetch QB) first.", "warn")
        return {}

    # Dynamic type map — Check/Expense/CC ka endpoint expense_target se decide
    expense_wafeq = "expense" if expense_target == "expense" else "journal"
    emit(f"Expense mapping: Check/Expense/CC → Wafeq '{expense_wafeq}'", "info")
    DYNAMIC_TYPE_MAP = {**QBO_TO_WAFEQ_TYPE}
    DYNAMIC_TYPE_MAP["check"]             = expense_wafeq
    DYNAMIC_TYPE_MAP["expense"]           = expense_wafeq
    DYNAMIC_TYPE_MAP["creditcardexpense"] = expense_wafeq

    all_txns = idx["bills"]
    total    = len(all_txns)

    # Group by Wafeq target type
    type_groups: dict[str, list] = {}
    for txn_id, txn in all_txns.items():
        qbo_type = str(txn.get("qbo_type") or "bill").lower().replace(" ", "")
        waf_type = DYNAMIC_TYPE_MAP.get(qbo_type, "bill")
        type_groups.setdefault(waf_type, []).append(txn_id)

    emit(f"QB transactions: {total} total", "info")
    for wt, ids in type_groups.items():
        emit(f"  → {wt}: {len(ids)} records", "info")

    # Fetch Wafeq records per type
    wafeq_records: dict[str, list] = {}
    wafeq_maps:    dict[str, dict] = {}

    for waf_type, endpoint in WAFEQ_ENDPOINT_MAP.items():
        if waf_type not in type_groups:
            continue
        emit(f"═══ Fetching Wafeq {waf_type}s ({endpoint}) ═══", "info")
        try:
            recs = _fetch_wafeq_records(api_key, endpoint, emit)
            wafeq_records[waf_type] = recs
            wafeq_maps[waf_type]    = _build_maps(recs, waf_type)
            emit(
                f"  {len(recs)} Wafeq {waf_type}s fetched | "
                f"external_id: {len(wafeq_maps[waf_type]['external_id'])} | "
                f"doc_number: {len(wafeq_maps[waf_type]['docnum'])} unique",
                "ok"
            )
        except Exception as e:
            emit(f"  Failed to fetch {endpoint}: {e}", "err")
            wafeq_records[waf_type] = []
            wafeq_maps[waf_type]    = _build_maps([], waf_type)

    # Match each QB transaction
    matched = no_match = duplicate = 0
    emit(f"═══ Matching {total} QB records ═══", "info")

    for i, (txn_id, txn) in enumerate(all_txns.items(), 1):
        qbo_type = str(txn.get("qbo_type") or "bill").lower().replace(" ", "")
        waf_type = DYNAMIC_TYPE_MAP.get(qbo_type, "bill")
        maps     = wafeq_maps.get(waf_type, _build_maps([], waf_type))

        qb_txn_id  = str(txn.get("qb_bill_id") or "").strip()
        doc_number = str(txn.get("doc_number") or "").strip()
        contact    = str(txn.get("vendor_name") or txn.get("customer_name") or "").strip()
        txn_date   = _date_norm(txn.get("txn_date", ""))
        amount     = _amount_norm(txn.get("total_amt") or txn.get("total_amount") or 0)

        emit(
            f"  [{i}/{total}] QB {qbo_type} | doc={doc_number or '—'} | "
            f"{contact or '?'} | {txn_date or '—'} | → Wafeq {waf_type}",
            "info"
        )

        status, result, try_num, note = _match_record(
            qb_txn_id, doc_number, contact, txn_date, amount, maps, waf_type, emit
        )

        if status == "matched":
            txn["match_status"]  = "matched"
            txn["wafeq_bill_id"] = result.get("id")
            txn["wafeq_type"]    = waf_type
            txn["wafeq_record"]  = _rec_summary(result, waf_type)
            txn["match_note"]    = note
            txn["match_try"]     = try_num
            emit(f"    ✓ Try {try_num}: {note} → {txn['wafeq_bill_id']}", "ok")
            matched += 1
        elif status == "duplicate":
            txn["match_status"]     = "duplicate"
            txn["wafeq_bill_id"]    = None
            txn["wafeq_type"]       = waf_type
            txn["wafeq_duplicates"] = [_rec_summary(h, waf_type) for h in result]
            txn["match_note"]       = f"{len(result)} duplicates: {note}"
            txn["match_try"]        = try_num
            emit(f"    ⚠ Try {try_num}: {len(result)} duplicates — {note}", "warn")
            duplicate += 1
        else:
            txn["match_status"]  = "no_match"
            txn["wafeq_bill_id"] = None
            txn["wafeq_type"]    = waf_type
            txn["match_note"]    = (
                f"No match: external_id='{qb_txn_id}' doc='{doc_number}' "
                f"contact='{contact}' date='{txn_date}' amount='{amount}'"
            )
            txn["match_try"] = 5
            emit(f"    ✗ No match — flagged for manual review", "warn")
            no_match += 1

    # Save
    wafeq_total = sum(len(v) for v in wafeq_records.values())
    idx["match_summary"] = {
        "total":              total,
        "matched":            matched,
        "no_match":           no_match,
        "duplicate":          duplicate,
        "wafeq_total":        wafeq_total,
        "external_id_mapped": sum(len(m["external_id"]) for m in wafeq_maps.values()),
    }
    save_index(realm_id, idx)
    upsert_company(realm_id, {
        "stats": {
            **idx.get("summary", {}),
            "matched":   matched,
            "no_match":  no_match,
            "duplicate": duplicate,
        }
    })

    emit(
        f"═══ Matching complete ═══ "
        f"✓ Matched: {matched} | ✗ No match: {no_match} | ⚠ Duplicate: {duplicate}",
        "ok"
    )
    return idx["match_summary"]
