"""
core/auth_users.py — Local user management
==========================================
Users stored in data/users.json (NOT .env)
Supports: admin role, regular users, password change, audit log
"""
import json
import hashlib
import secrets
import logging
from pathlib import Path
from datetime import datetime, timezone

log = logging.getLogger("auth_users")

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import DATA_DIR

log = logging.getLogger(__name__)

USERS_FILE = Path(DATA_DIR) / "users.json"
AUDIT_FILE = Path(DATA_DIR) / "audit.json"


def _hash(password: str) -> str:
    """SHA-256 hash for passwords."""
    return hashlib.sha256(password.encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_users() -> dict:
    if not USERS_FILE.exists():
        # Bootstrap from env AUTH_USERS if users.json doesn't exist
        raw = os.environ.get("AUTH_USERS", "admin:admin123")
        users = {}
        for pair in raw.split(","):
            pair = pair.strip()
            if ":" in pair:
                u, p = pair.split(":", 1)
                u = u.strip()
                users[u] = {
                    "password_hash": _hash(p.strip()),
                    "role":          "admin" if u == "admin" else "user",
                    "created_at":    _now(),
                    "last_login":    None,
                }
        USERS_FILE.write_text(json.dumps(users, indent=2))
        return users
    return json.loads(USERS_FILE.read_text())


def _save_users(users: dict):
    USERS_FILE.write_text(json.dumps(users, indent=2))


def _load_audit() -> list:
    if not AUDIT_FILE.exists():
        return []
    return json.loads(AUDIT_FILE.read_text())


def _append_audit(entry: dict):
    audit = _load_audit()
    audit.append(entry)
    # Keep last 10000 entries
    if len(audit) > 10000:
        audit = audit[-10000:]
    AUDIT_FILE.write_text(json.dumps(audit, indent=2))


# ── Public API ─────────────────────────────────────────────────────────────────

def authenticate(username: str, password: str) -> dict | None:
    """Returns user dict if credentials valid, else None."""
    users = _load_users()
    user  = users.get(username)
    if not user:
        return None
    if user["password_hash"] != _hash(password):
        return None
    # Update last_login
    users[username]["last_login"] = _now()
    _save_users(users)
    return {"username": username, "role": user["role"]}


def get_user(username: str) -> dict | None:
    users = _load_users()
    u = users.get(username)
    if not u:
        return None
    return {"username": username, "role": u["role"], "created_at": u.get("created_at"), "last_login": u.get("last_login")}


def list_users() -> list:
    users = _load_users()
    return [
        {
            "username":   u,
            "role":       d["role"],
            "created_at": d.get("created_at"),
            "last_login": d.get("last_login"),
        }
        for u, d in users.items()
    ]


def create_user(username: str, password: str, role: str = "user") -> tuple[bool, str]:
    """Returns (success, message)."""
    if not username or not password:
        return False, "Username and password required"
    if len(password) < 6:
        return False, "Password must be at least 6 characters"
    users = _load_users()
    if username in users:
        return False, f"User '{username}' already exists"
    users[username] = {
        "password_hash": _hash(password),
        "role":          role,
        "created_at":    _now(),
        "last_login":    None,
    }
    _save_users(users)
    return True, f"User '{username}' created"


def change_password(username: str, old_password: str, new_password: str) -> tuple[bool, str]:
    """Returns (success, message)."""
    users = _load_users()
    user  = users.get(username)
    if not user:
        return False, "User not found"
    if user["password_hash"] != _hash(old_password):
        return False, "Current password incorrect"
    if len(new_password) < 6:
        return False, "New password must be at least 6 characters"
    users[username]["password_hash"] = _hash(new_password)
    _save_users(users)
    return True, "Password changed successfully"


def admin_reset_password(admin_user: str, target_user: str, new_password: str) -> tuple[bool, str]:
    """Admin can reset any user's password without knowing old one."""
    users = _load_users()
    if users.get(admin_user, {}).get("role") != "admin":
        return False, "Admin access required"
    if target_user not in users:
        return False, f"User '{target_user}' not found"
    if len(new_password) < 6:
        return False, "Password must be at least 6 characters"
    users[target_user]["password_hash"] = _hash(new_password)
    _save_users(users)
    return True, f"Password reset for '{target_user}'"


def delete_user(admin_user: str, target_user: str) -> tuple[bool, str]:
    users = _load_users()
    if users.get(admin_user, {}).get("role") != "admin":
        return False, "Admin access required"
    if target_user not in users:
        return False, "User not found"
    if target_user == admin_user:
        return False, "Cannot delete yourself"
    del users[target_user]
    _save_users(users)
    return True, f"User '{target_user}' deleted"


# ── Audit logging ──────────────────────────────────────────────────────────────

def log_action(username: str, action: str, details: dict = None):
    """Record user action to audit.json and Python logger (app.log)."""
    entry = {
        "ts":       _now(),
        "user":     username,
        "action":   action,
        "details":  details or {},
    }
    _append_audit(entry)
    log.info(f"AUDIT user={username} action={action} details={details or {}}")


def get_audit_log(limit: int = 500, username: str = None) -> list:
    audit = _load_audit()
    if username:
        audit = [e for e in audit if e.get("user") == username]
    return list(reversed(audit))[:limit]
