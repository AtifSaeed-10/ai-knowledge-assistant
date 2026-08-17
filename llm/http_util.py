"""Shared HTTP helpers for provider implementations."""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx

from llm.errors import (
    CATEGORY_AUTH,
    CATEGORY_CONNECTION,
    CATEGORY_MALFORMED,
    CATEGORY_MODEL_UNAVAILABLE,
    CATEGORY_PROVIDER_UNAVAILABLE,
    CATEGORY_QUOTA,
    CATEGORY_RATE_LIMIT,
    CATEGORY_TIMEOUT,
    LLMError,
    NonRetryableLLMError,
    RetryableLLMError,
)
from llm.sanitize import redact_secrets, safe_error_message


def classify_http_error(
    status_code: int,
    body: str,
    *,
    provider: str,
) -> LLMError:
    text = redact_secrets(body or "")
    lowered = text.lower()
    quota = "quota" in lowered or "resource_exhausted" in lowered or status_code == 402

    if status_code in {400, 422}:
        return NonRetryableLLMError(
            f"{provider} rejected the request",
            category=CATEGORY_MALFORMED,
            provider=provider,
            status_code=status_code,
        )
    if status_code in {401, 403}:
        return LLMError(
            f"{provider} authentication failed",
            category=CATEGORY_AUTH,
            provider=provider,
            retry_same=False,
            allow_fallback=True,
            status_code=status_code,
        )
    if status_code == 404:
        return LLMError(
            f"{provider} model unavailable",
            category=CATEGORY_MODEL_UNAVAILABLE,
            provider=provider,
            retry_same=False,
            allow_fallback=True,
            status_code=status_code,
        )
    if status_code in {408, 409}:
        return RetryableLLMError(
            f"{provider} timed out",
            category=CATEGORY_TIMEOUT,
            provider=provider,
            status_code=status_code,
        )
    if status_code == 429 or quota:
        return RetryableLLMError(
            f"{provider} rate limited" if not quota else f"{provider} quota exhausted",
            category=CATEGORY_QUOTA if quota else CATEGORY_RATE_LIMIT,
            provider=provider,
            status_code=status_code,
        )
    if status_code >= 500:
        return RetryableLLMError(
            f"{provider} unavailable",
            category=CATEGORY_PROVIDER_UNAVAILABLE,
            provider=provider,
            status_code=status_code,
        )
    return LLMError(
        f"{provider} request failed",
        category=CATEGORY_PROVIDER_UNAVAILABLE,
        provider=provider,
        retry_same=False,
        allow_fallback=True,
        status_code=status_code,
    )


def map_httpx_error(exc: BaseException, *, provider: str) -> LLMError:
    if isinstance(exc, LLMError):
        return exc
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return RetryableLLMError(
            f"{provider} timed out",
            category=CATEGORY_TIMEOUT,
            provider=provider,
        )
    if isinstance(exc, (httpx.ConnectError, httpx.NetworkError)):
        return RetryableLLMError(
            f"{provider} connection failed",
            category=CATEGORY_CONNECTION,
            provider=provider,
        )
    return RetryableLLMError(
        f"{provider} request failed: {safe_error_message(exc)}",
        category=CATEGORY_PROVIDER_UNAVAILABLE,
        provider=provider,
        retry_same=False,
    )


def raise_for_status(response: httpx.Response, *, provider: str) -> None:
    if response.status_code < 400:
        return
    body = ""
    try:
        body = response.text
    except Exception:
        body = ""
    raise classify_http_error(response.status_code, body, provider=provider)


def raise_for_stream_status(response: httpx.Response, *, provider: str) -> None:
    if response.status_code < 400:
        return
    body = ""
    try:
        raw = response.read()
        body = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    except Exception:
        body = ""
    raise classify_http_error(response.status_code, body, provider=provider)


def iter_sse_data_lines(response: httpx.Response) -> Iterator[str]:
    for raw in response.iter_lines():
        line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        line = (line or "").strip()
        if not line or line.startswith(":"):
            continue
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload and payload != "[DONE]":
                yield payload


def parse_json(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
