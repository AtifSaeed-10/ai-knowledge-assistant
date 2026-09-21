"""Small HTTP helpers for web search. Errors stay out of the chat path."""

from __future__ import annotations

from typing import Any

import httpx

from llm.sanitize import redact_secrets, safe_error_message


class WebSearchError(Exception):
    def __init__(self, message: str, *, provider: str, status_code: int | None = None):
        super().__init__(redact_secrets(message))
        self.provider = provider
        self.status_code = status_code


def get_json(
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    timeout: float,
    provider: str,
) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, headers=headers, params=params)
    except Exception as exc:
        raise WebSearchError(
            f"{provider} request failed: {safe_error_message(exc)}",
            provider=provider,
        ) from exc
    return _read_json(response, provider=provider)


def post_json(
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout: float,
    provider: str,
) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=headers, json=body)
    except Exception as exc:
        raise WebSearchError(
            f"{provider} request failed: {safe_error_message(exc)}",
            provider=provider,
        ) from exc
    return _read_json(response, provider=provider)


def _read_json(response: httpx.Response, *, provider: str) -> dict[str, Any]:
    if response.status_code >= 400:
        raise WebSearchError(
            f"{provider} returned {response.status_code}",
            provider=provider,
            status_code=response.status_code,
        )
    try:
        data = response.json()
    except Exception as exc:
        raise WebSearchError(
            f"{provider} returned invalid JSON",
            provider=provider,
            status_code=response.status_code,
        ) from exc
    return data if isinstance(data, dict) else {}
