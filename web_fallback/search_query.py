"""Turn a chat question into search queries. No topic names."""

from __future__ import annotations

import re

from evidence_state import normalize_evidence_text

_FILLER_RE = re.compile(
    r"\b("
    r"can you|could you|would you|please|kindly|"
    r"tell me|give me|show me|name the|names of|"
    r"what are|what is|who are|who is|which are|"
    r"i need|i want"
    r")\b",
    re.I,
)
_YEAR_RANGE_RE = re.compile(r"\b(19|20)\d{2}\s*[-–—to]+\s*(19|20)\d{2}\b", re.I)
_LAST_N_RE = re.compile(r"\b(last|latest|recent|past)\s+\d{1,3}\b", re.I)
_RECENCY_RE = re.compile(
    r"\b(last|latest|current|today|tonight|yesterday|now|live|recent)\b",
    re.I,
)
_LIST_HINT_RE = re.compile(
    r"\b(list|ranking|rankings|ranked|winners|winner|champions|champion|"
    r"prime ministers|presidents|timeline)\b",
    re.I,
)
_SPACE_RE = re.compile(r"\s+")


def _clean_question(question: str) -> str:
    text = _FILLER_RE.sub(" ", question or "")
    text = text.replace("'", " ").replace("’", " ")
    text = re.sub(r"[?!.:,;]+", " ", text)
    return _SPACE_RE.sub(" ", text).strip()


def looks_like_list_question(question: str) -> bool:
    text = normalize_evidence_text(question)
    if _YEAR_RANGE_RE.search(text):
        return True
    if _LAST_N_RE.search(text):
        return True
    return bool(_LIST_HINT_RE.search(text))


def looks_like_recency_question(question: str) -> bool:
    """True for 'latest / last / today' facts, not for a numbered series or year span."""
    text = normalize_evidence_text(question)
    if not text:
        return False
    if _YEAR_RANGE_RE.search(text):
        return False
    if _LAST_N_RE.search(text):
        return False
    return bool(_RECENCY_RE.search(text))


def search_queries(question: str) -> list[str]:
    """
    One or two search strings. The second is a 'list of …' form when the
    question looks like a ranking or series, which search engines rank better.
    """
    cleaned = _clean_question(question)
    if not cleaned:
        cleaned = (question or "").strip()
    queries: list[str] = []
    if looks_like_recency_question(question) and cleaned:
        from datetime import datetime, timezone

        year = datetime.now(timezone.utc).year
        for extra in (cleaned, f"{cleaned} {year}"):
            if extra.lower() not in {q.lower() for q in queries}:
                queries.append(extra)
        return queries[:3]
    for item in (cleaned, question.strip() if question else ""):
        text = _SPACE_RE.sub(" ", item).strip()
        if text and text.lower() not in {q.lower() for q in queries}:
            queries.append(text)
    if looks_like_list_question(question) and cleaned:
        listed = f"list of {cleaned}"
        if listed.lower() not in {q.lower() for q in queries}:
            queries.append(listed)
    return queries[:3]
