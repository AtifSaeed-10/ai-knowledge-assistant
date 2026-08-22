"""
Deterministic claim → source-span → PDF region localization.

Separates the user's CLAIM (often paraphrased) from the SOURCE PASSAGE (chunk
text). Selects the minimum reliable source text, maps it to real PDF bboxes, and
reports confidence. Never invents coordinates or pretends precision when unsure.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from citation_resolver import _normalize_token, sanitize_quote
from evidence_mapping import (
    compact_contains,
    map_quote_to_regions,
    split_sentences,
)

# Localization hierarchy statuses (also used as quote_mapping_status when precise).
STATUS_EXACT = "exact"
STATUS_SENTENCE = "sentence"
STATUS_SEMANTIC_SPAN = "semantic_span"
STATUS_FALLBACK_CHUNK = "fallback_chunk"
STATUS_UNRESOLVED = "unresolved"

# Legacy mapping statuses passed through unchanged.
LEGACY_STATUSES = frozenset(
    {
        "none",
        "not_in_chunk",
        "no_evidence_data",
        "no_layout",
        "not_on_page",
        "rejected",
        "failed",
        "normalized",
        "fuzzy_compact",
        "hyphen_fuzzy",
    }
)

MIN_CONFIDENCE_SENTENCE = 0.42
MIN_CONFIDENCE_SEMANTIC = 0.52
MIN_HIGHLIGHT_CONFIDENCE = 0.52
MAX_SPANS = 3
MIN_WINDOW_WORDS = 4
MAX_WINDOW_WORDS = 22
MIN_INFORMATIVE_CLAIM_TOKENS = 4
MIN_INFORMATIVE_QUOTE_TOKENS = 5

STATUS_WEAK = "weak"
STATUS_UNSUPPORTED = "unsupported"

_MARKER_IN_SENTENCE_RE = re.compile(
    r"\[(E[1-9]\d*)(?:\:\s*\"([^\"\]]*)\")?\]",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*", re.IGNORECASE)

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "as",
        "by",
        "with",
        "from",
        "into",
        "than",
        "then",
        "also",
        "can",
        "may",
        "such",
        "use",
        "used",
        "using",
    }
)


@dataclass
class SpanCandidate:
    text: str
    score: float
    kind: str  # sentence | window
    segment_index: int | None = None


@dataclass
class TextSupport:
    """Document-agnostic claim↔chunk support (no PDF, no embeddings)."""

    status: str = STATUS_UNSUPPORTED
    confidence: float = 0.0
    coverage: float = 0.0
    span: str | None = None


@dataclass
class LocalizationResult:
    localization_status: str = STATUS_UNRESOLVED
    localization_confidence: float = 0.0
    quote_highlight_available: bool = False
    quote_regions: list[dict[str, Any]] = field(default_factory=list)
    source_spans: list[str] = field(default_factory=list)
    quote: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    segment_indices: list[int] = field(default_factory=list)


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            return word[: -len(suffix)]
    return word


def _tokens(text: str) -> set[str]:
    words = _WORD_RE.findall((text or "").lower())
    return {word for word in words if word not in _STOPWORDS and len(word) > 1}


def _token_overlap(claim_tokens: set[str], candidate_tokens: set[str]) -> int:
    if not claim_tokens or not candidate_tokens:
        return 0
    exact = len(claim_tokens & candidate_tokens)
    if exact:
        return exact
    claim_stems = {_stem(word) for word in claim_tokens}
    candidate_stems = {_stem(word) for word in candidate_tokens}
    return len(claim_stems & candidate_stems)


def token_f1(claim: str, candidate: str) -> float:
    """Deterministic token overlap F1 — no LLM, no embeddings."""
    claim_tokens = _tokens(claim)
    candidate_tokens = _tokens(candidate)
    if not claim_tokens or not candidate_tokens:
        return 0.0
    overlap = _token_overlap(claim_tokens, candidate_tokens)
    if overlap == 0:
        return 0.0
    precision = overlap / len(candidate_tokens)
    recall = overlap / len(claim_tokens)
    return (2.0 * precision * recall) / (precision + recall)


def extract_claim_near_marker(answer: str, evidence_id: str) -> str:
    """Extract the prose claim sentence surrounding a citation marker."""
    normalized_id = _normalize_token(evidence_id or "") or ""
    if not normalized_id:
        return ""

    marker_re = re.compile(
        rf"\[{re.escape(normalized_id)}(?:\:\s*\"[^\"\]]*\")?\]",
        re.IGNORECASE,
    )
    text = answer or ""
    match = marker_re.search(text)
    if not match:
        return ""

    before = text[: match.start()].strip()
    after = text[match.end() :].strip()

    if before:
        parts = re.split(r"(?<=[.!?])\s+", before)
        claim = parts[-1] if parts else before
    elif after:
        parts = re.split(r"(?<=[.!?])\s+", after)
        claim = parts[0] if parts else after
    else:
        claim = ""

    claim = _MARKER_IN_SENTENCE_RE.sub("", claim)
    claim = re.sub(r"\s+", " ", claim).strip(" .")
    if claim:
        parts = re.split(r"(?<=[.!?])\s+", claim)
        claim = (parts[-1] if parts else claim).strip(" .")
    return claim


def _word_windows(text: str) -> list[str]:
    words = _WORD_RE.findall(text or "")
    if len(words) < MIN_WINDOW_WORDS:
        stripped = (text or "").strip()
        return [stripped] if stripped else []
    windows: list[str] = []
    for size in range(MIN_WINDOW_WORDS, min(MAX_WINDOW_WORDS, len(words)) + 1):
        for index in range(0, len(words) - size + 1):
            windows.append(" ".join(words[index : index + size]))
    return windows


def _score_sentence_candidates(
    claim: str,
    chunk_text: str,
    segments: list[dict[str, Any]] | None,
) -> list[SpanCandidate]:
    candidates: list[SpanCandidate] = []
    seen: set[str] = set()

    for segment in segments or []:
        if not isinstance(segment, dict):
            continue
        sentence = (segment.get("text") or "").strip()
        if not sentence:
            continue
        key = sentence.casefold()
        if key in seen:
            continue
        seen.add(key)
        score = token_f1(claim, sentence)
        if compact_contains(sentence, claim) or compact_contains(claim, sentence):
            score = max(score, 0.85)
        candidates.append(
            SpanCandidate(
                text=sentence,
                score=score,
                kind="sentence",
                segment_index=segment.get("index"),
            )
        )

    for part in split_sentences(chunk_text, min_chars=MIN_WINDOW_WORDS * 3):
        sentence = (part.get("text") or "").strip()
        if not sentence:
            continue
        key = sentence.casefold()
        if key in seen:
            continue
        seen.add(key)
        score = token_f1(claim, sentence)
        candidates.append(
            SpanCandidate(
                text=sentence,
                score=score,
                kind="sentence",
            )
        )
    candidates.sort(key=lambda item: (-item.score, len(item.text)))
    return candidates


def build_token_df(texts: list[str]) -> dict[str, int]:
    """Document frequency of tokens across a candidate pool."""
    df: dict[str, int] = {}
    for text in texts:
        for token in _tokens(text):
            df[token] = df.get(token, 0) + 1
    return df


def claim_token_coverage(
    claim: str,
    chunk_text: str,
    *,
    df: dict[str, int] | None = None,
    n_docs: int = 1,
) -> float:
    """
    Fraction of claim tokens present in the chunk.

    When a pool document-frequency map is provided, tokens that appear in
    many candidates contribute less — this is document-agnostic and does not
    hard-code any corpus.
    """
    claim_tokens = _tokens(claim)
    if not claim_tokens:
        return 0.0
    chunk_tokens = _tokens(chunk_text)
    chunk_stems = {_stem(token) for token in chunk_tokens}

    def present(token: str) -> bool:
        if token in chunk_tokens:
            return True
        return _stem(token) in chunk_stems

    if not df or n_docs <= 0:
        hits = sum(1 for token in claim_tokens if present(token))
        return hits / len(claim_tokens)

    weighted = 0.0
    total = 0.0
    for token in claim_tokens:
        idf = math.log((n_docs + 1) / (df.get(token, 0) + 1)) + 1.0
        total += idf
        if present(token):
            weighted += idf
    return weighted / total if total else 0.0


def is_informative_claim(claim: str, quote: str | None = None) -> bool:
    """Short/generic claims are too weak to justify hopping off the retrieval slot."""
    return (
        len(_tokens(claim)) >= MIN_INFORMATIVE_CLAIM_TOKENS
        or len(_tokens(quote or "")) >= MIN_INFORMATIVE_QUOTE_TOKENS
    )


def score_text_support(
    claim_text: str,
    chunk_text: str,
    quote: str | None = None,
) -> TextSupport:
    """
    Score whether a chunk supports a claim using quote containment and
    sentence-level token overlap. No PDF layouts, no embeddings, no
    document-specific rules.
    """
    claim = re.sub(r"\s+", " ", (claim_text or "").strip())
    chunk = chunk_text or ""
    cleaned_quote = sanitize_quote(quote) if quote else None
    if not claim and cleaned_quote:
        claim = cleaned_quote
    coverage = claim_token_coverage(claim, chunk)
    quote_hit = bool(cleaned_quote and compact_contains(chunk, cleaned_quote))
    quote_supports_claim = False
    if quote_hit and cleaned_quote and claim:
        if compact_contains(claim, cleaned_quote) or compact_contains(cleaned_quote, claim):
            quote_supports_claim = True
        elif claim_token_coverage(claim, cleaned_quote) >= 0.4:
            quote_supports_claim = True

    sentence_hits = _score_sentence_candidates(claim, chunk, None) if claim else []
    best = sentence_hits[0] if sentence_hits else None
    sentence_score = float(best.score) if best else 0.0
    sentence_span = best.text if best else None

    if quote_hit and (quote_supports_claim or not claim):
        return TextSupport(
            status=STATUS_EXACT,
            confidence=1.0,
            coverage=coverage,
            span=cleaned_quote,
        )

    if best and sentence_score >= MIN_CONFIDENCE_SENTENCE:
        status = STATUS_SENTENCE
        if compact_contains(best.text, claim) or compact_contains(claim, best.text):
            sentence_score = max(sentence_score, 0.85)
        return TextSupport(
            status=status,
            confidence=min(1.0, sentence_score),
            coverage=coverage,
            span=sentence_span,
        )

    if coverage >= 0.35 or sentence_score >= 0.25:
        return TextSupport(
            status=STATUS_WEAK,
            confidence=max(sentence_score, coverage * 0.5),
            coverage=coverage,
            span=sentence_span,
        )

    return TextSupport(
        status=STATUS_UNSUPPORTED,
        confidence=sentence_score,
        coverage=coverage,
        span=None,
    )


def _score_window_candidates(claim: str, chunk_text: str) -> list[SpanCandidate]:
    candidates: list[SpanCandidate] = []
    seen: set[str] = set()
    for window in _word_windows(chunk_text):
        key = window.casefold()
        if key in seen:
            continue
        seen.add(key)
        score = token_f1(claim, window)
        if compact_contains(chunk_text, window):
            candidates.append(SpanCandidate(text=window, score=score, kind="window"))
    candidates.sort(key=lambda item: (-item.score, len(item.text)))
    return candidates


def _spans_non_overlapping(selected: list[SpanCandidate]) -> list[SpanCandidate]:
    """Keep up to MAX_SPANS non-overlapping high-scoring windows."""
    if not selected:
        return []
    ordered = sorted(selected, key=lambda item: (-item.score, len(item.text)))
    kept: list[SpanCandidate] = []
    for candidate in ordered:
        if len(kept) >= MAX_SPANS:
            break
        text = candidate.text.casefold()
        if any(text in other.text.casefold() or other.text.casefold() in text for other in kept):
            continue
        kept.append(candidate)
    return kept


def _select_span_candidates(
    claim: str,
    chunk_text: str,
    segments: list[dict[str, Any]] | None,
) -> tuple[list[SpanCandidate], str, float]:
    """Return chosen source spans and preliminary status + confidence."""
    if not claim.strip():
        return [], STATUS_UNRESOLVED, 0.0

    sentence_hits = _score_sentence_candidates(claim, chunk_text, segments)
    if sentence_hits and sentence_hits[0].score >= MIN_CONFIDENCE_SENTENCE:
        best = sentence_hits[0]
        # Prefer a tighter window inside the best sentence when claim is partial.
        inner = _score_window_candidates(claim, best.text)
        if inner and inner[0].score >= MIN_CONFIDENCE_SEMANTIC:
            if len(inner[0].text) < len(best.text) * 0.85:
                chosen = _spans_non_overlapping([inner[0]])
                return chosen, STATUS_SEMANTIC_SPAN, inner[0].score
        return [best], STATUS_SENTENCE, best.score

    window_hits = _score_window_candidates(claim, chunk_text)
    strong = [row for row in window_hits if row.score >= MIN_CONFIDENCE_SEMANTIC]
    if strong:
        chosen = _spans_non_overlapping(strong[: MAX_SPANS * 2])
        if len(chosen) > 1:
            avg = sum(item.score for item in chosen) / len(chosen)
            return chosen, STATUS_SEMANTIC_SPAN, avg
        return chosen[:1], STATUS_SEMANTIC_SPAN, chosen[0].score

    return [], STATUS_UNRESOLVED, 0.0


def _map_source_spans_to_regions(
    spans: list[SpanCandidate],
    *,
    chunk_text: str,
    layouts: dict[Any, Any],
    page_start: int,
    page_end: int,
    ranges: list[dict[str, Any]] | None,
    segments: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[int], str]:
    """Map selected source text spans to PDF regions (may be multi-span)."""
    all_regions: list[dict[str, Any]] = []
    segment_indices: list[int] = []
    match_types: list[str] = []

    for candidate in spans:
        if candidate.segment_index is not None:
            segment_indices.append(int(candidate.segment_index))
            seg = next(
                (
                    row
                    for row in (segments or [])
                    if isinstance(row, dict) and row.get("index") == candidate.segment_index
                ),
                None,
            )
            if (
                seg
                and seg.get("highlight_available")
                and candidate.kind == "sentence"
                and compact_contains(seg.get("text") or "", candidate.text)
            ):
                all_regions.extend(seg.get("regions") or [])
                match_types.append(str(seg.get("match_type") or STATUS_SENTENCE))
                continue

        if candidate.segment_index is None and segments:
            best_seg = None
            best_score = 0.0
            for seg in segments:
                if not isinstance(seg, dict) or not seg.get("highlight_available"):
                    continue
                score = token_f1(candidate.text, seg.get("text") or "")
                if score > best_score:
                    best_score = score
                    best_seg = seg
            if best_seg is not None and best_score >= 0.8:
                if best_seg.get("index") is not None:
                    segment_indices.append(int(best_seg["index"]))
                all_regions.extend(best_seg.get("regions") or [])
                match_types.append(str(best_seg.get("match_type") or STATUS_SENTENCE))
                continue

        mapped = map_quote_to_regions(
            candidate.text,
            chunk_text=chunk_text,
            layouts=layouts,
            page_start=page_start,
            page_end=page_end,
            ranges=ranges,
            segments=segments,
        )
        if mapped.get("quote_highlight_available") and mapped.get("regions"):
            all_regions.extend(mapped.get("regions") or [])
            match_types.append(str(mapped.get("match_type") or "exact"))

    if not all_regions:
        return [], segment_indices, "failed"

    # Deduplicate regions by rounded bbox.
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for region in all_regions:
        if not isinstance(region, dict):
            continue
        key = (
            region.get("page"),
            round(float(region.get("x0") or 0), 2),
            round(float(region.get("y0") or 0), 2),
            round(float(region.get("x1") or 0), 2),
            round(float(region.get("y1") or 0), 2),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(region)

    overall = match_types[0] if match_types else "exact"
    return unique, segment_indices, overall


def localize_claim_in_chunk(
    claim_text: str,
    chunk_text: str,
    *,
    quote: str | None = None,
    layouts: dict[Any, Any] | None = None,
    page_start: int = 1,
    page_end: int = 1,
    ranges: list[dict[str, Any]] | None = None,
    segments: list[dict[str, Any]] | None = None,
    chunk_highlight_available: bool = False,
) -> LocalizationResult:
    """
    Core localization: claim + chunk → minimum source span(s) → PDF regions.

    Hierarchy:
      A. Verified verbatim quote (exact)
      B. Sentence-level token match
      C. Small semantic span (sliding word windows)
      D. Unresolved / fallback (no precise highlight)
    """
    result = LocalizationResult()
    claim = re.sub(r"\s+", " ", (claim_text or "").strip())
    chunk = chunk_text or ""
    cleaned_quote = sanitize_quote(quote) if quote else None

    # A. Exact / verified quote path
    if cleaned_quote and compact_contains(chunk, cleaned_quote):
        mapped = map_quote_to_regions(
            cleaned_quote,
            chunk_text=chunk,
            layouts=layouts or {},
            page_start=page_start,
            page_end=page_end,
            ranges=ranges,
            segments=segments,
        )
        if mapped.get("quote_highlight_available") and mapped.get("regions"):
            pages = mapped.get("pages") or []
            result.localization_status = STATUS_EXACT
            result.localization_confidence = 1.0
            result.quote_highlight_available = True
            result.quote_regions = list(mapped.get("regions") or [])
            result.source_spans = [cleaned_quote]
            result.quote = cleaned_quote
            if pages:
                result.page_start = min(pages)
                result.page_end = max(pages)
            return result
        # Quote verified in chunk but PDF map failed — fall through with quote as claim hint.
        claim = claim or cleaned_quote

    if not claim:
        if chunk_highlight_available:
            result.localization_status = STATUS_FALLBACK_CHUNK
        else:
            result.localization_status = STATUS_UNRESOLVED
        return result

    spans, status, confidence = _select_span_candidates(claim, chunk, segments)
    if not spans or confidence < MIN_HIGHLIGHT_CONFIDENCE:
        if chunk_highlight_available:
            result.localization_status = STATUS_FALLBACK_CHUNK
            result.localization_confidence = confidence
        else:
            result.localization_status = STATUS_UNRESOLVED
            result.localization_confidence = confidence
        return result

    result.source_spans = [item.text for item in spans]
    result.quote = result.source_spans[0] if result.source_spans else cleaned_quote
    result.localization_confidence = confidence
    result.localization_status = status

    if not layouts:
        result.quote_highlight_available = False
        return result

    regions, segment_indices, _match = _map_source_spans_to_regions(
        spans,
        chunk_text=chunk,
        layouts=layouts,
        page_start=page_start,
        page_end=page_end,
        ranges=ranges,
        segments=segments,
    )
    if not regions:
        if chunk_highlight_available:
            result.localization_status = STATUS_FALLBACK_CHUNK
        else:
            result.localization_status = STATUS_UNRESOLVED
        return result

    pages = sorted(
        {
            int(item["page"])
            for item in regions
            if isinstance(item, dict) and item.get("page") is not None
        }
    )
    result.quote_highlight_available = True
    result.quote_regions = regions
    result.segment_indices = segment_indices
    if pages:
        result.page_start = min(pages)
        result.page_end = max(pages)
    return result


def localization_cache_key(*, claim_text: str, quote: str | None = None) -> str:
    """Cache key text: prefer verified quote, else claim prose."""
    cleaned_quote = sanitize_quote(quote) if quote else None
    if cleaned_quote:
        return cleaned_quote
    return re.sub(r"\s+", " ", (claim_text or "").strip())
