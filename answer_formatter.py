"""
Post-process LLM answers: remove prose quote dumps, keep citations concise.

The model often pastes long verbatim passages in the answer body even when
citation markers exist. This module cleans that before validation.
"""

from __future__ import annotations

import re

from citation_resolver import format_citation_marker, split_unclosed_bracket

# Citation markers are preserved verbatim during cleanup.
_MARKER_RE = re.compile(
    r"\[(E[1-9]\d*)(?:\:\s*\"([^\"\]]*)\")?\]",
    re.IGNORECASE,
)

# Straight double-quoted spans in prose.
_PROSE_QUOTE_RE = re.compile(r'"([^"\n]{40,}?)"')

_MAX_MARKER_QUOTE_CHARS = 120
_MIN_PROSE_QUOTE_CHARS = 40


def _truncate_quote(text: str, limit: int = _MAX_MARKER_QUOTE_CHARS) -> str:
    collapsed = re.sub(r"\s+", " ", (text or "").strip())
    if len(collapsed) <= limit:
        return collapsed
    cut = collapsed[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:")
    return cut + "…" if cut else collapsed[: limit - 1].rstrip() + "…"


def truncate_marker_quotes(text: str, limit: int = _MAX_MARKER_QUOTE_CHARS) -> str:
    """Shorten overly long verbatim quotes inside [E#:\"...\"] markers."""

    def replace(match: re.Match[str]) -> str:
        evidence_id = match.group(1)
        quote = match.group(2)
        if quote is None:
            return format_citation_marker(evidence_id)
        trimmed = _truncate_quote(quote, limit)
        return format_citation_marker(evidence_id, trimmed)

    return _MARKER_RE.sub(replace, text or "")


def remove_prose_quote_dumps(text: str, min_chars: int = _MIN_PROSE_QUOTE_CHARS) -> str:
    """
    Remove long inline quoted passages from prose.

    Citation markers are split out first so their quotes are never stripped.
    """
    if not text:
        return ""

    parts: list[str] = []
    last = 0
    for match in _MARKER_RE.finditer(text):
        segment = text[last : match.start()]
        if segment:
            parts.append(_PROSE_QUOTE_RE.sub(_replace_prose_quote, segment))
        parts.append(match.group(0))
        last = match.end()
    tail = text[last:]
    if tail:
        parts.append(_PROSE_QUOTE_RE.sub(_replace_prose_quote, tail))
    return "".join(parts)


def _replace_prose_quote(match: re.Match[str]) -> str:
    quoted = (match.group(1) or "").strip()
    if len(quoted) < _MIN_PROSE_QUOTE_CHARS:
        return match.group(0)
    # Drop the dump; the surrounding prose should already paraphrase the idea.
    return ""


def collapse_blank_lines(text: str) -> str:
    cleaned = re.sub(r"[ \t]+\n", "\n", text or "")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"  +", " ", cleaned)
    return cleaned.strip()


def polish_answer_text(text: str) -> str:
    """Apply safe formatting cleanups before citation validation."""
    complete, hold = split_unclosed_bracket(text or "")
    polished = remove_prose_quote_dumps(complete)
    polished = truncate_marker_quotes(polished)
    polished = collapse_blank_lines(polished)
    return polished + hold
