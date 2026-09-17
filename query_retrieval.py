"""
Item 4 — query-type-aware retrieval profiles.

Conversational intent (definition / why / listing) still lives in
conversation_query.py. This module only decides how to search: which
lexical phrases to boost, whether to prefer front-matter pages, and
which extra BM25 probes to run so structured questions are not drowned
by later-chapter bag-of-words hits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from config import (
    FRONT_MATTER_MAX_PAGE,
    QUERY_TYPE_CANDIDATE_BOOST,
    QUERY_TYPE_RESERVED_SLOTS,
    RRF_K,
)

KIND_DEFAULT = "default"
KIND_FRONT_MATTER = "front_matter"
KIND_FIGURE = "figure_ref"
KIND_ARTICLE = "article_ref"
KIND_SECTION_REF = "section_ref"
KIND_WHY_AUTHOR = "why_author"
KIND_LISTING = "listing"

_STOPWORDS = frozenset(
    """
    a an the and or but if then so of to for from in on at by with as
    is are was were be been being do does did doing can could should would
    will just about into over after before than too very also not no
    please me my we our you your what which who whom whose when where
    why how this that these those it its they them their
    any some there really still even much many does did does
    """.split()
)

_FIGURE_NUM_RE = re.compile(
    r"\bfigures?\s*(?:number|no\.?|#)?\s*(\d+)\b",
    re.I,
)
_WHICH_FIGURE_RE = re.compile(
    r"\bwhich figure\b|"
    r"\bfigure (?:that |which )?(?:depicts?|shows?|illustrates?)\b|"
    r"\b(?:depicts?|shows?|illustrates?)\b.{0,40}\bfigure\b",
    re.I,
)
_ARTICLE_RE = re.compile(r"\barticles?\s+(\d+[a-z]?)\b", re.I)
_SECTION_REF_RE = re.compile(
    r"\b(weeks?|lectures?|sessions?|modules?|units?|chapters?|lessons?|"
    r"days?|topics?)\s*(?:number|no\.?|#)?\s*"
    r"(\d+|[ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|"
    r"ten|eleven|twelve)\b",
    re.I,
)
_WORD_OR_ROMAN_NUMBER = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "i": "1",
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "v": "5",
    "vi": "6",
    "vii": "7",
    "viii": "8",
    "ix": "9",
    "x": "10",
    "xi": "11",
    "xii": "12",
}


def _canonical_section_number(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value.isdigit():
        return str(int(value))
    return _WORD_OR_ROMAN_NUMBER.get(value, value)


def parse_section_ref(question: str) -> tuple[str, str] | None:
    """Return (unit_label, digit) for 'week 4' / 'lecture four' style lookups."""
    match = _SECTION_REF_RE.search(question or "")
    if not match:
        return None
    label = re.sub(r"s$", "", match.group(1).lower())
    number = _canonical_section_number(match.group(2))
    if not number:
        return None
    return label, number


def section_ref_phrases(label: str, number: str) -> list[str]:
    """Lexical forms that usually appear as syllabus headings."""
    word = next(
        (name for name, digit in _WORD_OR_ROMAN_NUMBER.items() if digit == number and name.isalpha() and len(name) > 2),
        "",
    )
    forms = [
        f"{label} {number}",
        f"{label}{number}",
        f"{label}-{number}",
    ]
    if word:
        forms.append(f"{label} {word}")
    return forms
_FRONT_MATTER_RE = re.compile(
    r"\b(dedicat(?:e|ed|ion)|preface|foreword|acknowledg(?:e|ements?)|"
    r"this (?:book|edition)|title page|front matter)\b",
    re.I,
)
_WHY_AUTHOR_RE = re.compile(
    r"\bwhy does (?:the )?(?:author|writer|book|text|historian)s?\b|"
    r"\bwhy (?:is|are|did) (?:the )?(?:author|writer)\b|"
    r"\bwhy (?:does|did) (?:he|she|they) (?:use|choose|spell|write|prefer)\b",
    re.I,
)
_LISTING_RE = re.compile(
    r"\b(types?|kinds?|categor(?:y|ies)|list(?:ing)?|enumerate|"
    r"how many|how much|"
    r"(?:two|three|four|five|six|seven|eight|nine|ten|\d+)\s+"
    r"(?:long[- ]term |main |key |primary )?"
    r"(?:causes?|reasons?|factors?|points?|types?|kinds?|compromises?))\b",
    re.I,
)
_QUOTED_RE = re.compile(r'"([^"]{2,80})"|“([^”]{2,80})”')
_INSTEAD_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9\-']{1,40})\s+instead of\s+"
    r"([A-Za-z][A-Za-z0-9\-']{1,40}(?:\s+[A-Za-z][A-Za-z0-9\-']{1,40})?)",
    re.I,
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class RetrievalQuery:
    kind: str = KIND_DEFAULT
    phrases: list[str] = field(default_factory=list)
    extra_queries: list[str] = field(default_factory=list)
    page_min: int | None = None
    page_max: int | None = None
    candidate_k_boost: int = 0
    reserved_slots: int = 0
    figure_number: int | None = None
    article_number: str | None = None
    section_label: str | None = None
    section_number: str | None = None


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


_QUERY_META_TOKENS = frozenset(
    {
        "figure",
        "figures",
        "number",
        "depicts",
        "shows",
        "illustrates",
        "article",
        "articles",
        "list",
        "listing",
    }
)


def _content_ngram_phrases(question: str) -> list[str]:
    tokens = _tokens(question)
    phrases: list[str] = []
    run: list[str] = []

    def _flush(span: list[str]) -> None:
        for n in (2, 3):
            for i in range(0, len(span) - n + 1):
                phrases.append(" ".join(span[i : i + n]))

    for tok in tokens:
        if tok in _STOPWORDS or tok in _QUERY_META_TOKENS:
            _flush(run)
            run = []
            continue
        run.append(tok)
    _flush(run)
    return phrases


def classify_retrieval_query(question: str) -> RetrievalQuery:
    text = (question or "").strip()
    if not text:
        return RetrievalQuery()

    figure_number = None
    fig_match = _FIGURE_NUM_RE.search(text)
    if fig_match:
        figure_number = int(fig_match.group(1))

    article_number = None
    art_match = _ARTICLE_RE.search(text)
    if art_match:
        article_number = art_match.group(1).lower()

    section = parse_section_ref(text)

    if figure_number is not None or _WHICH_FIGURE_RE.search(text):
        kind = KIND_FIGURE
    elif article_number is not None:
        kind = KIND_ARTICLE
    elif section is not None:
        kind = KIND_SECTION_REF
    elif _FRONT_MATTER_RE.search(text):
        kind = KIND_FRONT_MATTER
    elif _WHY_AUTHOR_RE.search(text):
        kind = KIND_WHY_AUTHOR
    elif _LISTING_RE.search(text):
        kind = KIND_LISTING
    else:
        kind = KIND_DEFAULT

    phrases: list[str] = []
    extra: list[str] = []
    page_min = None
    page_max = None
    boost = 0
    reserved = 0

    for match in _QUOTED_RE.finditer(text):
        quoted = (match.group(1) or match.group(2) or "").strip()
        if quoted:
            phrases.append(quoted)

    phrases.extend(_content_ngram_phrases(text))

    if kind == KIND_FIGURE:
        if figure_number is not None:
            phrases.append(f"figure {figure_number}")
            extra.append(f"figure {figure_number}")
        else:
            extra.append("figure")
        reserved = QUERY_TYPE_RESERVED_SLOTS
        boost = QUERY_TYPE_CANDIDATE_BOOST
    elif kind == KIND_ARTICLE:
        phrases.append(f"article {article_number}")
        extra.append(f"article {article_number}")
        reserved = QUERY_TYPE_RESERVED_SLOTS
        boost = QUERY_TYPE_CANDIDATE_BOOST
    elif kind == KIND_SECTION_REF and section is not None:
        label, number = section
        forms = section_ref_phrases(label, number)
        phrases.extend(forms)
        extra.extend(forms[:2])
        reserved = QUERY_TYPE_RESERVED_SLOTS
        boost = QUERY_TYPE_CANDIDATE_BOOST
    elif kind == KIND_FRONT_MATTER:
        phrases.extend(
            ["dedicated to", "sixth edition", "this edition", "dedication"]
        )
        extra.append(
            "dedication dedicated scholars preface acknowledgements foreword"
        )
        page_min = 1
        page_max = FRONT_MATTER_MAX_PAGE
        reserved = QUERY_TYPE_RESERVED_SLOTS
        boost = QUERY_TYPE_CANDIDATE_BOOST
    elif kind == KIND_WHY_AUTHOR:
        extra.append("author")
        instead = _INSTEAD_RE.search(text)
        if instead:
            left = instead.group(1).strip()
            right = instead.group(2).strip()
            phrases.extend([left, right, f"{left} instead of {right}"])
            extra.append(f"{left} {right}")
        reserved = QUERY_TYPE_RESERVED_SLOTS
        boost = QUERY_TYPE_CANDIDATE_BOOST
    elif kind == KIND_LISTING:
        reserved = min(2, QUERY_TYPE_RESERVED_SLOTS)
        boost = QUERY_TYPE_CANDIDATE_BOOST

    # Dedup phrases while preserving order; drop empty/single-stopword.
    cleaned: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        key = " ".join(_tokens(phrase))
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(phrase.strip())

    extra_clean: list[str] = []
    extra_seen: set[str] = set()
    for item in extra:
        key = item.strip().lower()
        if not key or key == text.lower() or key in extra_seen:
            continue
        extra_seen.add(key)
        extra_clean.append(item.strip())

    from wide_recall import lexical_probe_queries

    for probe in lexical_probe_queries(text):
        key = probe.strip().lower()
        if not key or key == text.lower() or key in extra_seen:
            continue
        extra_seen.add(key)
        extra_clean.append(probe.strip())
        if probe.strip() not in cleaned:
            cleaned.append(probe.strip())

    if extra_clean and reserved <= 0:
        reserved = min(3, QUERY_TYPE_RESERVED_SLOTS)
        boost = max(boost, QUERY_TYPE_CANDIDATE_BOOST)

    return RetrievalQuery(
        kind=kind,
        phrases=cleaned,
        extra_queries=extra_clean,
        page_min=page_min,
        page_max=page_max,
        candidate_k_boost=boost,
        reserved_slots=reserved,
        figure_number=figure_number,
        article_number=article_number,
        section_label=section[0] if section else None,
        section_number=section[1] if section else None,
    )


def hit_to_fused_candidate(
    hit: dict[str, Any],
    *,
    source: str = "query_type",
    rank: int = 1,
) -> dict[str, Any]:
    """Shape a BM25/dense hit like fuse_results output so rerank can score it."""
    sources = list(hit.get("sources") or [])
    if source not in sources:
        sources.append(source)
    rrf = float(hit.get("rrf_score") or 0.0)
    if rrf <= 0:
        rrf = 1.0 / (RRF_K + max(1, rank))
    return {
        "id": hit["id"],
        "text": hit.get("text") or "",
        "metadata": hit.get("metadata") or {},
        "dense_distance": hit.get("dense_distance"),
        "bm25_score": hit.get("bm25_score"),
        "rrf_score": rrf,
        "sources": sorted(set(sources)),
    }


def ensure_typed_hits_in_pool(
    fused: list[dict[str, Any]],
    typed_hits: list[dict[str, Any]],
    *,
    reserved: int,
    limit: int,
) -> list[dict[str, Any]]:
    """
    Reserve fused-pool slots for query-type hits that hybrid search missed.

    Existing RRF order is preserved for everyone else. Typed hits that are
    already in the pool are left in place.
    """
    if not typed_hits or reserved <= 0 or limit <= 0:
        return list(fused)[:limit] if limit else list(fused)

    existing = {item["id"] for item in fused}
    newcomers: list[dict[str, Any]] = []
    for index, hit in enumerate(typed_hits, start=1):
        chunk_id = hit.get("id")
        if not chunk_id or chunk_id in existing:
            continue
        newcomers.append(hit_to_fused_candidate(hit, rank=index))
        existing.add(chunk_id)
        if len(newcomers) >= reserved:
            break

    if not newcomers:
        return list(fused)[:limit]

    keep_n = max(0, limit - len(newcomers))
    kept = [item for item in fused if item["id"] not in {n["id"] for n in newcomers}]
    kept = kept[:keep_n]
    return (newcomers + kept)[:limit]
