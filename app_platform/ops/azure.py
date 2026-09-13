"""
Azure credit card for the operator dashboard.

This is the VM hosting credit, not an Azure OpenAI balance. Remaining is
either a manual spend override or an estimate from hours since the VM
start date times the hourly SKU price.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app_platform import settings


def _parse_when(value: str | None) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(raw[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def azure_status() -> dict[str, Any]:
    start = max(0.0, float(settings.AZURE_CREDIT_START_USD))
    hourly = max(0.0, float(settings.AZURE_VM_HOURLY_USD))
    expires = settings.AZURE_CREDIT_EXPIRES or None
    started = _parse_when(settings.AZURE_CREDIT_STARTED_AT)
    spend_override = settings.AZURE_SPEND_USD
    now = datetime.now(timezone.utc)

    if spend_override is not None:
        spend = max(0.0, float(spend_override))
        source = "manual"
    elif started is not None:
        hours = max(0.0, (now - started).total_seconds() / 3600.0)
        spend = hours * hourly
        source = "estimate"
    else:
        spend = None
        source = "unknown"

    remaining = None if spend is None else max(0.0, start - spend)
    monthly = hourly * 24.0 * 30.0

    return {
        "credit_start_usd": round(start, 2),
        "spend_usd": None if spend is None else round(spend, 2),
        "remaining_usd": None if remaining is None else round(remaining, 2),
        "expires": expires,
        "hourly_usd": hourly,
        "estimated_monthly_usd": round(monthly, 2),
        "started_at": started.date().isoformat() if started else None,
        "source": source,
        "as_of": now.isoformat(),
    }
