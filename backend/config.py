"""
config.py — Central configuration
==================================
All credentials loaded from .env file.
Never hardcode secrets here.

Setup:
  1. Copy .env.example to .env
  2. Fill in your values in .env
  3. Run the app — config.py reads from .env automatically
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent / ".env")


def _require(key: str) -> str:
    """Get env var or raise clear error if missing."""
    val = os.getenv(key, "").strip()
    if not val:
        raise RuntimeError(
            f"\n\n  Missing required env variable: {key}\n"
            f"  Add it to your .env file.\n"
            f"  See .env.example for reference.\n"
        )
    return val


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


# ===========================================================================
# QuickBooks
# ===========================================================================
CLIENT_ID       = _require("QB_CLIENT_ID")
CLIENT_SECRET   = _require("QB_CLIENT_SECRET")
ENVIRONMENT     = _optional("QB_ENVIRONMENT", "production")
NGROK_URL       = _require("NGROK_URL")
REDIRECT_PATH   = "/callback"
REDIRECT_URI    = NGROK_URL + REDIRECT_PATH

INTUIT_AUTH_URL  = "https://appcenter.intuit.com/connect/oauth2"
INTUIT_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

QB_BASE_URLS = {
    "sandbox":    "https://sandbox-quickbooks.api.intuit.com",
    "production": "https://quickbooks.api.intuit.com",
}
QB_BASE_URL  = QB_BASE_URLS[ENVIRONMENT]
QB_PAGE_SIZE = 100

# ===========================================================================
# Flask
# ===========================================================================
FLASK_PORT       = int(_optional("FLASK_PORT", "8000"))
FLASK_SECRET_KEY = _optional("FLASK_SECRET_KEY", "dev-secret-change-in-production")

# ===========================================================================
# Database  (PostgreSQL — filled after Docker setup)
# ===========================================================================
DATABASE_URL = _optional("DATABASE_URL", "")

# ===========================================================================
# Wafeq
# ===========================================================================
WAFEQ_BASE_URL  = "https://api.wafeq.com/v1"
WAFEQ_PAGE_SIZE = 100

# ===========================================================================
# Local paths
# ===========================================================================
DATA_DIR      = "data"
TOKENS_DIR    = "data/tokens"
DOWNLOADS_DIR = "downloads"
