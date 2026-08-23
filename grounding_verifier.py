"""
Item 7 — grounding verification and anti-refusal.

A blanket "not found" answer is invalid when the recall pool already
contains supporting text. Repair by one constrained retry, then by an
extractive excerpt. Never invent facts that are not in the passages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from claim_localizer import (
    STATUS_EXACT,
    STATUS_SENTENCE,
    score_text_support,
)
from config import CLAIM_SUPPORT_MIN
from conversation_query import (
    INTENT_EXAMPLE,
    INTENT_HOW,
    INTENT_KEY_POINTS,
    INTENT_LISTING,
    INTENT_SUMMARY,
    INTENT_WHY,
    TurnAnalysis,
)
from evidence_focus import ROLE_SUPPORT, passage_roles
from evidence_mapping import make_snippet
from evidence_state import looks_like_evidence_refusal

SYNTHESIS_INTENTS = {INTENT_SUMMARY, INTENT_KEY_POINTS}
_ROLE_GATED_INTENTS = {INTENT_LISTING, INTENT_EXAMPLE, INTENT_WHY, INTENT_HOW}
_MIN_SYNTHESIS_TOKENS = 12
_MAX_EXCERPT_CHARS = 400
_PARTIAL_ANSWER_WORDS = 40
_REMAINDER_TOKEN_LIMIT = 8

ANTI_REFUSAL_ADDENDUM = """

IMPORTANT — grounding check:
A previous draft said the information was not in the document, but the
passages above DO contain supporting material for this request.
Do not say the information was not found.
Answer only from those passages.
If the user asked for a summary or key points, synthesize from the passages
in context; do not look for a heading titled Summary.
If you are still uncertain, quote the most relevant one or two sentences
rather than refusing. Never invent facts that are not in the passages.
"""

EVIDENCE_PRESENT_LEAD = "The provided passages discuss this. Supporting excerpt:"


@dataclass
class GroundingHit:
    supported: bool
    reason: str
    chunk_id: str = ""
    evidence_id: str = ""
    span: str = ""
    snippet: str = ""
    passage: str = ""
    score: float = 0.0


def is_blanket_refusal(answer: str) -> bool:
    """True only for a short, evidence-empty refusal — not a partial answer."""
    text = (answer or "").strip()
    if not text or not looks_like_evidence_refusal(text):
        return False
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) <= _PARTIAL_ANSWER_WORDS:
        return True
    remainder = text.lower()
    for snippet in (
        "i don't have enough information in the provided context",
        "i couldn't find that in the provided document",
        "the provided document does not give a specific example of this",
        "couldn't find",
        "could not find",
        "don't have enough information",
        "do not have enough information",
        "no relevant information",
        "not in the provided document",
        "not in the provided context",
    ):
        remainder = remainder.replace(snippet, " ")
    leftover = re.findall(r"[a-z0-9]+", remainder)
    return len(leftover) <= _REMAINDER_TOKEN_LIMIT


def _row_text(row: dict[str, Any]) -> str:
    for key in ("text", "chunk_text", "snippet", "quote"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _pool_rows(
    sources: list[dict[str, Any]] | None,
    recall_candidates: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in list(recall_candidates or []) + list(sources or []):
        if not isinstance(row, dict):
            continue
        chunk_id = str(row.get("chunk_id") or "")
        key = chunk_id or f"{row.get('document_id')}:{row.get('page')}:{id(row)}"
        if key not in merged:
            merged[key] = dict(row)
            continue
        current = merged[key]
        old = _row_text(current)
        new = _row_text(row)
        if len(new) > len(old):
            current["text"] = new
        for field, value in row.items():
            if current.get(field) in (None, "", [], False) and value not in (None, "", []):
                current[field] = value
    return list(merged.values())


def _role_allows_chunk(
    chunk: str,
    question: str,
    analysis: TurnAnalysis | None,
) -> bool:
    if analysis is None or analysis.intent not in _ROLE_GATED_INTENTS:
        return True
    roles = passage_roles([chunk], question, analysis)
    return bool(roles) and roles[0] == ROLE_SUPPORT


_QUESTION_LEAD_RE = re.compile(
    r"^(?:please\s+)?(?:can you |could you )?(?:tell me |give me )?"
    r"(?:how much|how many|how long|how|what are|what is|what's|whats|"
    r"what|why does|why do|why|when|where|who|which|"
    r"list|summarize|summarise|explain)\b[\s:?]*",
    re.I,
)


def _question_focus(question: str) -> str:
    """Strip interrogative lead-in so support scoring uses the asked-about content."""
    text = (question or "").strip()
    text = _QUESTION_LEAD_RE.sub("", text, count=1).strip(" ?")
    return text or (question or "").strip()


def _token_count(text: str) -> int:
    return len(re.findall(r"[a-z0-9]+", (text or "").lower()))


def find_context_support(
    question: str,
    *,
    sources: list[dict[str, Any]] | None = None,
    recall_candidates: list[dict[str, Any]] | None = None,
    analysis: TurnAnalysis | None = None,
) -> GroundingHit:
    """Whether the recall pool contains material that makes a blanket refusal invalid."""
    rows = _pool_rows(sources, recall_candidates)
    intent = analysis.intent if analysis else ""
    question_text = _question_focus(question)

    if intent in SYNTHESIS_INTENTS:
        for row in rows:
            text = _row_text(row)
            if _token_count(text) >= _MIN_SYNTHESIS_TOKENS:
                return GroundingHit(
                    supported=True,
                    reason="synthesis_context",
                    chunk_id=str(row.get("chunk_id") or ""),
                    evidence_id=str(row.get("evidence_id") or ""),
                    span="",
                    snippet=make_snippet(text),
                    passage=text,
                    score=1.0,
                )
        return GroundingHit(supported=False, reason="empty_synthesis_context")

    best: GroundingHit | None = None
    for row in rows:
        text = _row_text(row)
        if not text.strip():
            continue
        if not _role_allows_chunk(text, question or "", analysis):
            continue
        support = score_text_support(question_text, text)
        score = max(float(support.confidence or 0.0), float(support.coverage or 0.0))
        strong = (
            support.status in {STATUS_EXACT, STATUS_SENTENCE}
            or float(support.coverage or 0.0) >= CLAIM_SUPPORT_MIN
            or float(support.confidence or 0.0) >= CLAIM_SUPPORT_MIN
        )
        if not strong:
            continue
        hit = GroundingHit(
            supported=True,
            reason=str(support.status or "supported"),
            chunk_id=str(row.get("chunk_id") or ""),
            evidence_id=str(row.get("evidence_id") or ""),
            span=(support.span or "").strip(),
            snippet=make_snippet(text),
            passage=text,
            score=score,
        )
        if best is None or hit.score > best.score:
            best = hit
    return best or GroundingHit(supported=False, reason="unsupported")


def format_extractive_answer(hit: GroundingHit) -> str:
    """Conservative repair: show a supporting excerpt, do not synthesize new claims."""
    excerpt = (hit.span or hit.snippet or hit.passage or "").strip()
    # polish_answer_text strips long double-quoted prose dumps; keep this
    # excerpt unquoted so the repair still contains the supporting span.
    excerpt = excerpt.replace('"', "").replace("\u201c", "").replace("\u201d", "")
    if len(excerpt) > _MAX_EXCERPT_CHARS:
        excerpt = excerpt[:_MAX_EXCERPT_CHARS].rsplit(" ", 1)[0].strip()
    marker = f" [{hit.evidence_id}]" if hit.evidence_id else ""
    if not excerpt:
        return (EVIDENCE_PRESENT_LEAD + marker).strip()
    return f"{EVIDENCE_PRESENT_LEAD}\n\n{excerpt}{marker}"


def verify_and_repair_refusal(
    answer: str,
    *,
    question: str,
    prompt: str | None = None,
    sources: list[dict[str, Any]] | None = None,
    recall_candidates: list[dict[str, Any]] | None = None,
    analysis: TurnAnalysis | None = None,
    generate_fn: Callable[[str], str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """
    Keep a refusal when context does not support the question.
    If context does support it, retry once, then fall back to an excerpt.
    """
    if not is_blanket_refusal(answer):
        return answer, {"action": "keep", "reason": "not_refusal"}

    hit = find_context_support(
        question,
        sources=sources,
        recall_candidates=recall_candidates,
        analysis=analysis,
    )
    if not hit.supported:
        return answer, {"action": "keep", "reason": hit.reason}

    if generate_fn and (prompt or "").strip():
        try:
            retried = (generate_fn(prompt + ANTI_REFUSAL_ADDENDUM) or "").strip()
        except Exception:
            retried = ""
        if retried and not is_blanket_refusal(retried):
            print(
                f"Grounding: invalid refusal repaired by retry ({hit.reason})"
            )
            return retried, {
                "action": "retry",
                "reason": hit.reason,
                "chunk_id": hit.chunk_id,
                "evidence_id": hit.evidence_id,
            }

    repaired = format_extractive_answer(hit)
    print(
        f"Grounding: invalid refusal replaced with excerpt ({hit.reason})"
    )
    return repaired, {
        "action": "extractive",
        "reason": hit.reason,
        "chunk_id": hit.chunk_id,
        "evidence_id": hit.evidence_id,
    }
