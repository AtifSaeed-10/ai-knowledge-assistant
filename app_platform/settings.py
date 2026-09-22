"""
Deployment settings for the platform layer.

Every value is env-driven so the same image can move between hosts and
databases without code changes.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _env_str(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _env_int(name: str, default: int) -> int:
    raw = _env_str(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env_str(name).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: list[str]) -> list[str]:
    raw = _env_str(name)
    if not raw:
        return list(default)
    items: list[str] = []
    for part in raw.split(","):
        value = part.strip()
        if value and value not in items:
            items.append(value)
    return items


def _env_float(name: str, default: float) -> float:
    raw = _env_str(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_optional_float(name: str) -> float | None:
    raw = _env_str(name)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


# ========================
# Datastore
# ========================
# sqlite:///relative/path.db or sqlite:////absolute/path.db today.
# A postgres:// URL is accepted by database/connection.py once a driver exists.
DATABASE_URL = _env_str("DATABASE_URL", "sqlite:///./data/documents.db")

# ========================
# HTTP
# ========================
CORS_ORIGINS = _env_csv("CORS_ORIGINS", [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://www.docusage.tech",
    "https://docusage.tech",
])

# ========================
# Auth
# ========================
# "supabase" verifies Bearer JWTs. "none" keeps guest-only mode (local dev).
AUTH_PROVIDER = _env_str("AUTH_PROVIDER", "none").lower()
SUPABASE_URL = _env_str("SUPABASE_URL")
SUPABASE_JWT_SECRET = _env_str("SUPABASE_JWT_SECRET")

# Anonymous trial can be closed off entirely without touching route code.
GUEST_TRIAL_ENABLED = _env_bool("GUEST_TRIAL_ENABLED", True)

# ========================
# Quotas
# ========================
QUOTA_GUEST_MAX_PDFS = _env_int("QUOTA_GUEST_MAX_PDFS", 1)
QUOTA_GUEST_MAX_QUESTIONS = _env_int("QUOTA_GUEST_MAX_QUESTIONS", 15)
QUOTA_GUEST_MAX_WEB_QUESTIONS = _env_int("QUOTA_GUEST_MAX_WEB_QUESTIONS", 30)
QUOTA_USER_MAX_PDFS = _env_int("QUOTA_USER_MAX_PDFS", 5)
QUOTA_USER_MAX_QUESTIONS_MONTHLY = _env_int("QUOTA_USER_MAX_QUESTIONS_MONTHLY", 100)
QUOTA_USER_MAX_WEB_QUESTIONS_MONTHLY = _env_int(
    "QUOTA_USER_MAX_WEB_QUESTIONS_MONTHLY",
    100,
)
QUOTA_MAX_PDF_MB = _env_int("QUOTA_MAX_PDF_MB", 25)

# ========================
# Operator dashboard
# ========================
# Comma-separated Google emails. Only these accounts can load /admin.
ADMIN_EMAILS = _env_csv("ADMIN_EMAILS", ["saeedatif199@gmail.com"])

# Azure VM credit card on the dashboard. Remaining is estimated unless
# AZURE_SPEND_USD is set; live billing APIs are not wired yet.
AZURE_CREDIT_START_USD = _env_float("AZURE_CREDIT_START_USD", 100.0)
AZURE_CREDIT_EXPIRES = _env_str("AZURE_CREDIT_EXPIRES", "2027-09-05")
AZURE_VM_HOURLY_USD = _env_float("AZURE_VM_HOURLY_USD", 0.05)
AZURE_CREDIT_STARTED_AT = _env_str("AZURE_CREDIT_STARTED_AT")
AZURE_SPEND_USD = _env_optional_float("AZURE_SPEND_USD")


def auth_enabled() -> bool:
    """True when signed-in users are supported by this deployment."""
    return AUTH_PROVIDER == "supabase" and bool(SUPABASE_JWT_SECRET or SUPABASE_URL)


def max_pdf_bytes() -> int:
    return max(1, QUOTA_MAX_PDF_MB) * 1024 * 1024
