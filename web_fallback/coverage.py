"""
Whether retrieved PDF text actually bears on the question.

RAG always returns *some* top-k chunks. That is not the same as covering
the asked fact. Used when Web is on so an unrelated file does not block
a question it does not cover, without naming any topic in product code.
"""

from __future__ import annotations

import re
from typing import Any

from evidence_state import normalize_evidence_text

# Function words and other tokens that appear in almost any English question.
_STOP = frozenset(
    """
    a an the and or but if to of in on for from with about into over after
    before during without within who whom whose what when where why how
    which this that these those it its they them their is are was were be
    been being do did does doing have has had having will would can could
    should may might must shall not no nor so than then also just only
    any all each few more most other some such own same both you your
    yours our ours yourself yourselves please kindly someone anyone
    everybody ask asked asking
    """.split()
)

# Common words that should not count as covering a specific ask
# ("world" matches "world war"; "won" matches almost any history PDF).
_WEAK = frozenset(
    """
    world war life time year years people person history country state
    after before during about which their there would could should other
    first later early many some also into from with this that they them
    made make take give come came told tell said know known fact facts
    information details event events won win wins model models method
    methods data system systems latest current recent last next previous
    names name list lists ranking rank ranks number numbers numbered
    called show showing given prime price prices score scores match
    matches cost costs amount amounts value values rate rates
    """.split()
)

# These are too generic to prove a PDF covers an ask, but a web page that
# answers "latest price / net worth / last score" must actually mention them.
_WEB_FACT_TOKENS = frozenset(
    """
    price prices score scores match matches cost costs amount amounts
    value values rate rates worth net wealth fortune
    """.split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def content_tokens(text: str) -> set[str]:
    """Question terms that should appear in the files if the files answer it."""
    return _tokens(text, keep_fact_words=False)


def web_query_tokens(text: str) -> set[str]:
    """Question terms a web page must mention, including price/worth/score."""
    return _tokens(text, keep_fact_words=True)


def _tokens(text: str, *, keep_fact_words: bool) -> set[str]:
    tokens: set[str] = set()
    for word in _TOKEN_RE.findall(normalize_evidence_text(text)):
        if word.isdigit() and len(word) == 4:
            tokens.add(word)
            continue
        if any(ch.isdigit() for ch in word) and len(word) >= 2:
            tokens.add(word)
            continue
        if len(word) < 3:
            continue
        if word in _STOP:
            continue
        if word in _WEAK and not (keep_fact_words and word in _WEB_FACT_TOKENS):
            continue
        tokens.add(word)
    return tokens


def years_in(text: str) -> set[str]:
    return {word for word in _TOKEN_RE.findall(normalize_evidence_text(text)) if word.isdigit() and len(word) == 4}


def _period_aliases(text: str) -> set[str]:
    """Map common era abbreviations so 'ww2' matches 'World War II' / 1940s pages."""
    normalized = normalize_evidence_text(text)
    tokens = set(_TOKEN_RE.findall(normalized))
    aliases: set[str] = set()
    years = [int(token) for token in tokens if token.isdigit() and len(token) == 4]
    if (
        "ww2" in tokens
        or "wwii" in tokens
        or "world war ii" in normalized
        or "second world war" in normalized
        or any(1939 <= year <= 1945 for year in years)
    ):
        aliases.update({"ww2", "wwii"})
    if (
        "ww1" in tokens
        or "wwi" in tokens
        or "world war i" in normalized
        or "first world war" in normalized
        or any(1914 <= year <= 1918 for year in years)
    ):
        aliases.update({"ww1", "wwi"})
    return aliases


def passages_miss_question(question: str, passages: str) -> bool:
    """
    True when the retrieved text does not look like it covers the ask.

    Years and codes like "2022" / "ww2" must appear (or an equivalent era
    phrase). Related earlier pages are not enough. No content tokens means
    we cannot tell (not a miss).
    """
    asked = content_tokens(question)
    if not asked:
        return False
    blob = normalize_evidence_text(passages)
    if not blob.strip():
        return True
    blob_tokens = set(_TOKEN_RE.findall(blob)) | _period_aliases(passages)
    present = content_tokens(passages) | {word for word in blob_tokens if word in asked}
    asked_codes = {token for token in asked if any(ch.isdigit() for ch in token)}
    if asked_codes - blob_tokens:
        return True
    overlap = asked & present
    return len(overlap) * 2 < len(asked)


def passages_are_off_topic(question: str, passages: str) -> bool:
    """
    True when retrieved pages are about a different subject, not a later
    part of the same subject. Skip the long document generate in that case.
    """
    asked = content_tokens(question)
    if not asked:
        return False
    blob = normalize_evidence_text(passages)
    if not blob.strip():
        return True
    blob_tokens = set(_TOKEN_RE.findall(blob)) | _period_aliases(passages)
    asked_words = {token for token in asked if not any(ch.isdigit() for ch in token)}
    if not asked_words:
        return passages_miss_question(question, passages)
    return not (asked_words & blob_tokens)


def short_document_scope_note(document_result: dict[str, Any] | None) -> str:
    """One-line PDF scope note. No LLM."""
    names: list[str] = []
    seen: set[str] = set()
    result = document_result or {}
    for row in list(result.get("sources") or []) + list(result.get("recall_candidates") or []):
        if not isinstance(row, dict):
            continue
        name = str(row.get("filename") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= 2:
            break
    if not names:
        return "Your documents don't cover this question."
    if len(names) == 1:
        return (
            f"Your documents don't cover this question. "
            f"They focus on material in {names[0]}."
        )
    return (
        f"Your documents don't cover this question. "
        f"They focus on material in {names[0]} and {names[1]}."
    )


def passage_text_from_document(document_result: dict[str, Any] | None) -> str:
    parts: list[str] = []
    result = document_result or {}
    for row in list(result.get("recall_candidates") or []) + list(result.get("sources") or []):
        if not isinstance(row, dict):
            continue
        for key in ("text", "chunk_text", "snippet", "quote"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value)
                break
    return "\n".join(parts)
