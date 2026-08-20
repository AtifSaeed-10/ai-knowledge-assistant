"""
Deterministic claim-citation resolver.

LLM answers may contain [E1], [E1, E2], or [E1:"verbatim quote"] markers.
Only IDs that were assigned to retrieved passages are kept. Optional quotes
are preserved only when syntactically valid. Display numbers are the E-index
(E1 -> 1) and never change during streaming.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Iterator

# Quoted form: [E1:"quote"] or [E1|quote="quote"]. Quotes cannot contain " or ].
_QUOTED_MARKER_RE = re.compile(
    r"\[(E[1-9]\d*)\s*(?:\|\s*quote\s*=\s*|:\s*)\"([^\"\]]*)\"\]",
    re.IGNORECASE,
)
# Complete citation groups: [E1] or [E1, E2] (optional spaces).
_CITATION_GROUP_RE = re.compile(
    r"\[(\s*E[1-9]\d*(?:\s*,\s*E[1-9]\d*)*\s*)\]",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"E([1-9]\d*)", re.IGNORECASE)
_ADJACENT_DUP_RE = re.compile(
    r"(\[E[1-9]\d*(?:\:\"[^\"\]]*\")?\])\1+",
    re.IGNORECASE,
)
_COORD_QUOTE_RE = re.compile(
    r"\b(?:x0|y0|x1|y1|bbox|coord_space)\b",
    re.IGNORECASE,
)
# Model-emitted coordinate payloads are never trusted.
_COORD_MARKER_RE = re.compile(
    r"\[(E[1-9]\d*)[^\]]*\b(?:x0|y0|x1|y1|bbox|coord_space)\b[^\]]*\]",
    re.IGNORECASE,
)

MAX_QUOTE_CHARS = 400
MIN_QUOTE_COMPACT = 8


def evidence_id_for_index(index: int) -> str:
    """1-based retrieval-order id: E1, E2, ..."""
    if index < 1:
        raise ValueError("evidence index must be >= 1")
    return f"E{index}"


def display_number(evidence_id: str) -> int | None:
    match = re.fullmatch(r"E([1-9]\d*)", (evidence_id or "").strip(), re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def valid_ids_from_sources(sources: list[dict[str, Any]] | None) -> set[str]:
    ids: set[str] = set()
    for source in sources or []:
        raw = (source or {}).get("evidence_id")
        if not raw:
            continue
        normalized = _normalize_token(str(raw))
        if normalized:
            ids.add(normalized)
    return ids


def _normalize_token(token: str) -> str | None:
    match = _TOKEN_RE.fullmatch(token.strip())
    if not match:
        return None
    return f"E{int(match.group(1))}"


def sanitize_quote(quote: str | None) -> str | None:
    """Keep a short verbatim quote. Reject coordinates and empty/overlong text."""
    text = re.sub(r"\s+", " ", (quote or "").strip())
    if not text:
        return None
    if len(text) > MAX_QUOTE_CHARS:
        return None
    if '"' in text or "]" in text or "[" in text:
        return None
    if _COORD_QUOTE_RE.search(text):
        return None
    compact = re.sub(r"\s+", "", text)
    if len(compact) < MIN_QUOTE_COMPACT:
        return None
    return text


def format_citation_marker(evidence_id: str, quote: str | None = None) -> str:
    if quote:
        return f'[{evidence_id}:"{quote}"]'
    return f"[{evidence_id}]"


# Resolved answer markers: [E1] or [E1:"quote"]. Groups are already expanded.
_RESOLVED_MARKER_RE = re.compile(
    r"\[(E[1-9]\d*)(?:\:\"([^\"\]]*)\")?\]",
    re.IGNORECASE,
)


def quotes_by_evidence_id(text: str) -> dict[str, list[str]]:
    """Collect verbatim quotes actually used in a resolved answer, in order."""
    found: dict[str, list[str]] = {}
    for match in _RESOLVED_MARKER_RE.finditer(text or ""):
        evidence_id = _normalize_token(match.group(1) or "")
        if not evidence_id:
            continue
        quote = sanitize_quote(match.group(2))
        if not quote:
            continue
        found.setdefault(evidence_id, []).append(quote)
    return found


def attach_quotes_to_sources(
    sources: list[dict[str, Any]] | None,
    text: str,
) -> list[dict[str, Any]]:
    """Copy sources; set quote only on E-IDs the answer actually cited with a quote."""
    quotes = quotes_by_evidence_id(text)
    attached: list[dict[str, Any]] = []
    for source in sources or []:
        item = dict(source)
        evidence_id = _normalize_token(str(item.get("evidence_id") or ""))
        used = quotes.get(evidence_id or "") or []
        item["quote"] = used[0] if used else None
        attached.append(item)
    return attached


def _ids_from_group(body: str, valid_ids: set[str]) -> list[str]:
    kept: list[str] = []
    seen: set[str] = set()
    for match in _TOKEN_RE.finditer(body):
        evidence_id = f"E{int(match.group(1))}"
        if evidence_id not in valid_ids or evidence_id in seen:
            continue
        seen.add(evidence_id)
        kept.append(evidence_id)
    return kept


def resolve_evidence_markers(text: str, valid_ids: set[str]) -> str:
    """Drop invalid IDs; keep valid ones as [E1] or [E1:\"quote\"] in order."""

    def replace_quoted(match: re.Match[str]) -> str:
        evidence_id = _normalize_token(match.group(1) or "")
        if not evidence_id or evidence_id not in valid_ids:
            return ""
        quote = sanitize_quote(match.group(2))
        return format_citation_marker(evidence_id, quote)

    def replace_group(match: re.Match[str]) -> str:
        kept = _ids_from_group(match.group(1), valid_ids)
        if not kept:
            return ""
        return "".join(format_citation_marker(item) for item in kept)

    def replace_coord_marker(match: re.Match[str]) -> str:
        evidence_id = _normalize_token(match.group(1) or "")
        if not evidence_id or evidence_id not in valid_ids:
            return ""
        return format_citation_marker(evidence_id)

    resolved = _QUOTED_MARKER_RE.sub(replace_quoted, text or "")
    resolved = _COORD_MARKER_RE.sub(replace_coord_marker, resolved)
    resolved = _CITATION_GROUP_RE.sub(replace_group, resolved)
    return _ADJACENT_DUP_RE.sub(r"\1", resolved)


def split_unclosed_bracket(buffer: str) -> tuple[str, str]:
    """Hold back a trailing unclosed '[' so partial [E / [E1:\" never emit."""
    if not buffer:
        return "", ""
    last_open = buffer.rfind("[")
    if last_open == -1:
        return buffer, ""
    rest = buffer[last_open:]
    if "]" in rest:
        return buffer, ""
    return buffer[:last_open], rest


def resolve_answer(text: str, sources: list[dict[str, Any]] | None) -> str:
    valid_ids = valid_ids_from_sources(sources)
    complete, _hold = split_unclosed_bracket(text or "")
    return resolve_evidence_markers(complete, valid_ids)


class CitationStreamResolver:
    """Incremental resolver for token streams."""

    def __init__(self, sources: list[dict[str, Any]] | None):
        self.valid_ids = valid_ids_from_sources(sources)
        self._buffer = ""

    def feed(self, token: str) -> str:
        self._buffer += token or ""
        complete, hold = split_unclosed_bracket(self._buffer)
        self._buffer = hold
        return resolve_evidence_markers(complete, self.valid_ids)

    def close(self) -> str:
        complete, _hold = split_unclosed_bracket(self._buffer)
        self._buffer = ""
        return resolve_evidence_markers(complete, self.valid_ids)


def iter_resolved_stream(
    tokens: Iterable[str],
    sources: list[dict[str, Any]] | None,
) -> Iterator[str]:
    resolver = CitationStreamResolver(sources)
    for token in tokens:
        emitted = resolver.feed(token)
        if emitted:
            yield emitted
    tail = resolver.close()
    if tail:
        yield tail
