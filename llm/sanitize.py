"""Redact secrets from logs and exception text."""

from __future__ import annotations

import os
import re

_SECRET_ENV_NAMES = (
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "CEREBRAS_API_KEY",
    "OPENROUTER_API_KEY",
    "MISTRAL_API_KEY",
)

_PATTERNS = [
    re.compile(r"gsk_[A-Za-z0-9]+"),
    re.compile(r"sk-or-v1-[A-Za-z0-9]+"),
    re.compile(r"csk-[A-Za-z0-9_-]+"),
    re.compile(r"AIza[A-Za-z0-9_-]+"),
    re.compile(r"AQ\.[A-Za-z0-9_-]+"),
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"api[_-]?key[\s:=]+[^\s\"']+", re.IGNORECASE),
    re.compile(r"x-goog-api-key[\s:=]+[^\s\"']+", re.IGNORECASE),
    re.compile(r"Authorization[\s:=]+[^\s\"']+", re.IGNORECASE),
]


def _secret_values() -> list[str]:
    values: list[str] = []
    for name in _SECRET_ENV_NAMES:
        raw = (os.getenv(name) or "").strip()
        if raw:
            values.append(raw)
    return values


def redact_secrets(text: str | None) -> str:
    if not text:
        return ""
    redacted = str(text)
    for secret in _secret_values():
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    for pattern in _PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def safe_error_message(exc: BaseException) -> str:
    return redact_secrets(str(exc)) or type(exc).__name__
