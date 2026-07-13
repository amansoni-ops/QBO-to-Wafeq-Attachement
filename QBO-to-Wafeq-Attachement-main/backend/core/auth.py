"""
core/auth.py — QB token management
====================================
Token files location: qb_profiles/qb_tokens_{realm_id}.json
(Same as app.py — both must use identical path + filename)
"""

import json
import base64
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import CLIENT_ID, CLIENT_SECRET, INTUIT_TOKEN_URL, QB_BASE_URLS, ENVIRONMENT

# ── Token file location — MUST match app.py exactly ──────────────────────────
# app.py uses:  TOKENS_DIR = Path("qb_profiles")
#               token file: qb_profiles/qb_tokens_{realm_id}.json
TOKENS_DIR = Path("qb_profiles")
TOKENS_DIR.mkdir(exist_ok=True)


def _basic_header() -> str:
    return "Basic " + base64.b64encode(
        f"{CLIENT_ID}:{CLIENT_SECRET}".encode()
    ).decode()


def token_path(realm_id: str) -> Path:
    """Returns: qb_profiles/qb_tokens_{realm_id}.json  (same as app.py)"""
    return TOKENS_DIR / f"qb_tokens_{realm_id}.json"


def save_tokens(realm_id: str, data: dict):
    token_path(realm_id).write_text(json.dumps(data, indent=2))


def load_tokens(realm_id: str) -> dict | None:
    p = token_path(realm_id)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def is_token_valid(tokens: dict, buffer_sec: int = 120) -> bool:
    try:
        exp = datetime.fromisoformat(tokens["access_token_expires_at"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < (exp - timedelta(seconds=buffer_sec))
    except Exception:
        return False


def refresh_token(realm_id: str) -> dict:
    tokens = load_tokens(realm_id)
    if not tokens:
        raise RuntimeError(f"No tokens for realm {realm_id}")

    resp = requests.post(
        INTUIT_TOKEN_URL,
        headers={
            "Authorization": _basic_header(),
            "Content-Type":  "application/x-www-form-urlencoded",
            "Accept":        "application/json",
        },
        data={
            "grant_type":    "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Refresh failed ({resp.status_code}): {resp.text}")

    t = resp.json()
    updated = {
        **tokens,
        "access_token":            t["access_token"],
        "refresh_token":           t["refresh_token"],
        "access_token_expires_at": (
            datetime.now(timezone.utc) + timedelta(seconds=t.get("expires_in", 3600))
        ).isoformat(),
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }
    save_tokens(realm_id, updated)
    return updated


def get_access_token(realm_id: str) -> str:
    """Returns valid access token — auto-refreshes if expired."""
    tokens = load_tokens(realm_id)
    if not tokens:
        raise RuntimeError(
            f"No tokens found for realm {realm_id}.\n"
            f"Expected file: qb_profiles/qb_tokens_{realm_id}.json\n"
            f"Please reconnect QB from the dashboard."
        )
    if not is_token_valid(tokens):
        tokens = refresh_token(realm_id)
    return tokens["access_token"]


def fetch_company_info(access_token: str, realm_id: str) -> dict:
    base = QB_BASE_URLS[ENVIRONMENT]
    url  = f"{base}/v3/company/{realm_id}/companyinfo/{realm_id}"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        params={"minorversion": "65"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("CompanyInfo", {})
