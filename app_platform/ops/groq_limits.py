"""Parse Groq rate-limit headers into a small snapshot dict."""

from __future__ import annotations

from typing import Any, Mapping


def _header_map(headers: Mapping[str, Any] | None) -> dict[str, str]:
    if not headers:
        return {}
    mapped: dict[str, str] = {}
    for key, value in headers.items():
        if value is None:
            continue
        mapped[str(key).lower()] = str(value)
    return mapped


def _as_int(raw: str | None) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def parse_groq_limits(headers: Mapping[str, Any] | None) -> dict[str, Any]:
    values = _header_map(headers)
    return {
        "remaining_requests": _as_int(values.get("x-ratelimit-remaining-requests")),
        "limit_requests": _as_int(values.get("x-ratelimit-limit-requests")),
        "remaining_tokens": _as_int(values.get("x-ratelimit-remaining-tokens")),
        "limit_tokens": _as_int(values.get("x-ratelimit-limit-tokens")),
        "reset_requests": values.get("x-ratelimit-reset-requests"),
        "reset_tokens": values.get("x-ratelimit-reset-tokens"),
    }


def usage_tokens(response: Any) -> int:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0
    try:
        return int(getattr(usage, "total_tokens", 0) or 0)
    except (TypeError, ValueError):
        return 0


def store_groq_call(
    headers: Mapping[str, Any] | None,
    tokens: int = 0,
    error: str | None = None,
) -> None:
    try:
        from database.provider_store import record_provider_call

        record_provider_call("groq", parse_groq_limits(headers), tokens, error)
    except Exception:
        return
