"""Shared shapes for the web-fallback pass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ORIGIN_DOCUMENT = "document"
ORIGIN_WEB_FALLBACK = "web_fallback"
ORIGIN_MIXED = "mixed"

# Stream control frames. The frontend parser must know these so they never
# leak into the visible answer.
WEB_SOURCES_START = "__WEB_SOURCES__"
WEB_SOURCES_END = "__END_WEB_SOURCES__"


@dataclass(frozen=True)
class WebHit:
    title: str
    url: str
    snippet: str
    domain: str = ""
    provider: str = "mock"
    preview: bool = True
    retrieved_at: str | None = None
    tier: str = "preview"


@dataclass
class WebFallbackResult:
    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    origin: str = ORIGIN_WEB_FALLBACK
    reason: str = ""
    provider: str = "mock"
    preview: bool = True
    prompt: str | None = None
