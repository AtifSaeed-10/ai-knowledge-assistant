"""
Prompt for a live web pass.

The model may only use numbered web passages. Prose stays in DocuSage's
voice — no "the internet says" / "externally" phrasing.
"""

from __future__ import annotations

from web_fallback.types import WebHit
from web_fallback.urls import clean_snippet
from web_fallback.search_query import looks_like_recency_question

WEB_UNAVAILABLE_ANSWER = (
    "I couldn't find a web source that states this yet."
)

WEB_PREVIEW_ANSWER = (
    "Your documents don't cover this question. Web lookup is in preview, "
    "so this is not a live trusted-site answer yet."
)

WEB_GAP_PREVIEW_ANSWER = (
    "Web lookup is in preview, so I cannot add a live trusted-site "
    "answer for the part your documents do not cover yet."
)

_TIER_LABEL = {
    "t1": "official source",
    "t2": "reference source",
    "t3": "additional source",
    "unknown": "additional source",
}


def format_web_passages(hits: list[WebHit]) -> str:
    passages = []
    for index, hit in enumerate(hits, start=1):
        kind = _TIER_LABEL.get(hit.tier, "source")
        passages.append(
            f"[W{index}] {kind} — {hit.title} ({hit.domain or hit.url})\n"
            f"URL: {hit.url}\n"
            f"{(clean_snippet(hit.snippet or '') or '').strip()}"
        )
    return "\n\n".join(passages) if passages else "(no web passages)"


def _web_voice_rules() -> str:
    return (
        "Write in a calm, direct voice. Do not mention the web, browsers, "
        "search, external sources, or that these passages came from the internet.\n"
        "Do not use prior knowledge. If a passage does not support a fact, "
        "do not state that fact.\n"
        "If two passages disagree, prefer an official source over a reference "
        "source, and a reference source over an additional source. If it is "
        "still unclear, say so briefly.\n"
        "Do not use PDF evidence markers like [E1]. Do not put [W1], [W2], "
        "or any other source marker in the answer. Source cards are shown "
        "separately.\n"
    )


def _recency_rules() -> str:
    from datetime import datetime, timezone

    year = datetime.now(timezone.utc).year
    return (
        f"The question asks for a current or latest fact (today is {year}). "
        f"Use only passages dated {year} or {year - 1}, or undated live reports. "
        "Do not treat an older season, archive interview, or historical round-up "
        "as the latest. If no passage states a current dated fact, say you do "
        "not have a verified current source. Do not guess.\n"
    )


def build_web_prompt(question: str, hits: list[WebHit]) -> str:
    pool = format_web_passages(hits)
    recency = _recency_rules() if looks_like_recency_question(question) else ""
    return (
        "You answer using only the numbered web passages below.\n"
        "Answer the question directly, the way a normal web search would. "
        "Lead with the fact the user asked for (the number, name, score, or list). "
        "If they asked for a list, ranking, or a run of years, give a compact "
        "list from the passages (year or order first). Keep it short "
        "(roughly 80-180 words). Do not open with a document-miss apology. "
        "Do not say the passages are missing the answer if they contain it.\n"
        f"{_web_voice_rules()}"
        f"{recency}\n"
        f"Question:\n{question.strip()}\n\n"
        f"Web passages:\n{pool}\n"
    )


def build_web_gap_prompt(
    question: str,
    document_answer: str,
    hits: list[WebHit],
) -> str:
    """
    Fill only the part the document said it does not cover.

    The document-backed prose is concatenated later, not rewritten here.
    """
    pool = format_web_passages(hits)
    return (
        "The user's documents already answered part of this question. "
        "That document-backed answer is quoted below. Do not rewrite it, "
        "repeat it, or contradict it.\n"
        "Answer ONLY the part of the question the document said it does not "
        "cover, using only the numbered web passages.\n"
        f"{_web_voice_rules()}"
        f"{_recency_rules() if looks_like_recency_question(question) else ''}\n"
        f"Question:\n{question.strip()}\n\n"
        "Document-backed answer (keep this as-is; do not repeat it):\n"
        f"{document_answer.strip()}\n\n"
        f"Web passages:\n{pool}\n"
    )
