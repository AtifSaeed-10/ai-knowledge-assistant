"""
Document-first orchestrator for optional web fallback.

The RAG stack is not imported here. Callers run ask_question first, then
hand the result in. That keeps retrieval scoring unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from app_platform.ops.events import record_safe
from llm.errors import GENERATION_UNAVAILABLE
from web_fallback.citations import hit_to_source
from web_fallback.coverage import passage_text_from_document
from web_fallback.decision import (
    ACTION_CONTINUE,
    ACTION_DOCUMENT,
    ACTION_WEB,
    REASON_DOC_SUFFICIENT,
    decide_web_after_answer,
    decide_web_fallback,
    is_document_gap_answer,
)
from web_fallback.http import WebSearchError
from web_fallback.policy import get_domain_policy, select_hits
from web_fallback.prompt import (
    WEB_GAP_PREVIEW_ANSWER,
    WEB_PREVIEW_ANSWER,
    WEB_UNAVAILABLE_ANSWER,
    build_web_gap_prompt,
    build_web_prompt,
)
from web_fallback.provider import (
    PROVIDER_MOCK,
    PROVIDER_NONE,
    get_search_provider,
)
from web_fallback.search_query import looks_like_recency_question, search_queries
from web_fallback.types import ORIGIN_DOCUMENT, ORIGIN_MIXED, ORIGIN_WEB_FALLBACK, WebFallbackResult, WebHit


def log_web_decision(
    *,
    reason: str,
    action: str,
    hit_count: int = 0,
    provider: str | None = None,
    route: str = "/chat",
) -> None:
    print(
        f"Web fallback: action={action} reason={reason} "
        f"hits={hit_count} provider={provider or '-'}",
        flush=True,
    )
    record_safe(
        kind="web_fallback",
        route=route,
        category=reason,
        provider=provider,
        message=f"action={action} hits={hit_count}",
    )


def _limits() -> tuple[int, int, bool, int]:
    from config import (
        WEB_INCLUDE_DOMAIN_LIMIT,
        WEB_MAX_SOURCES,
        WEB_MIN_TRUSTED_HITS,
        WEB_SEARCH_RESTRICT_DOMAINS,
    )

    return (
        max(1, int(WEB_MAX_SOURCES)),
        max(1, int(WEB_MIN_TRUSTED_HITS)),
        bool(WEB_SEARCH_RESTRICT_DOMAINS),
        max(1, int(WEB_INCLUDE_DOMAIN_LIMIT)),
    )


def search_web(query: str) -> list[WebHit]:
    """
    Open web search. Blocklisted sites never become evidence.
    Official and reference pages still rank first when they match the ask.
    """
    provider = get_search_provider()
    queries = search_queries(query)
    recency = looks_like_recency_question(query)
    if provider.name in {PROVIDER_MOCK, PROVIDER_NONE}:
        return provider.search(queries[0] if queries else query, recency=recency)

    max_sources, _min_trusted, restrict, include_limit = _limits()
    policy = get_domain_policy()
    include = policy.trusted_hosts(include_limit) if restrict else None

    raw: list[WebHit] = []
    seen_urls: set[str] = set()
    try:
        for index, item in enumerate(queries):
            for hit in provider.search(
                item,
                include_domains=include,
                recency=recency and index > 0,
            ):
                key = (hit.url or "").strip().rstrip("/").lower()
                if not key or key in seen_urls:
                    continue
                seen_urls.add(key)
                raw.append(hit)
    except WebSearchError as exc:
        log_web_decision(
            reason="web_search_failed",
            action=ACTION_WEB,
            provider=provider.name,
        )
        print(f"Web search error: {exc}")
        return []

    selected = select_hits(
        raw,
        allow_t3=True,
        limit=max_sources,
        policy=policy,
        question=query,
    )
    if selected or include is None:
        return selected

    extra: list[WebHit] = []
    try:
        extra = provider.search(
            queries[0] if queries else query,
            include_domains=None,
            recency=False,
        )
    except WebSearchError as exc:
        print(f"Web search broaden error: {exc}")
        extra = []

    return select_hits(
        [*raw, *extra],
        allow_t3=True,
        limit=max_sources,
        policy=policy,
        question=query,
    )


_WEB_MARKER_RE = re.compile(r"\s*\[W[1-9]\d*\]")


def finalize_web_answer(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned or cleaned == GENERATION_UNAVAILABLE:
        return WEB_UNAVAILABLE_ANSWER
    cleaned = _WEB_MARKER_RE.sub("", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    return cleaned.strip()


def _document_miss_only(answer: str) -> bool:
    text = str(answer or "").strip()
    if not text:
        return False
    if not is_document_gap_answer(text):
        return False
    return "[e" not in text.lower()


def combine_document_and_web_answer(document_answer: str, web_answer: str) -> str:
    """Keep PDF prose when it added facts; drop a long document-miss apology."""
    doc = str(document_answer or "").strip()
    web = str(web_answer or "").strip()
    if not web or web == WEB_UNAVAILABLE_ANSWER:
        return doc
    if not doc:
        return web
    if web == doc or web in doc:
        return doc
    if _document_miss_only(doc):
        return web
    return f"{doc}\n\n{web}"


def merge_answer_sources(*groups: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for group in groups:
        for item in group or []:
            if not isinstance(item, dict):
                continue
            key = (
                str(item.get("kind") or ""),
                str(item.get("evidence_id") or ""),
                str(item.get("url") or ""),
                str(item.get("chunk_id") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
    return out


def _public_pdf_source(item: dict[str, Any]) -> dict[str, Any]:
    public = dict(item)
    public.pop("text", None)
    return public


def document_sources_for_gap(
    *,
    visible: list[dict[str, Any]] | None,
    original: list[dict[str, Any]] | None,
    answer: str,
) -> list[dict[str, Any]]:
    """
    PDF cards to keep when web fills a gap.

    Cited markers win. If the model discussed the files without markers,
    keep a few retrieved pages so the UI still shows what the PDF said.
    Full chunk text never leaves the server.
    """
    if visible:
        return [_public_pdf_source(item) for item in visible]
    from claim_validator import used_sources

    cited = used_sources(list(original or []), answer)
    if cited:
        return [_public_pdf_source(item) for item in cited]
    out: list[dict[str, Any]] = []
    for item in original or []:
        if not isinstance(item, dict):
            continue
        if not (item.get("filename") or item.get("document_id") or item.get("chunk_id")):
            continue
        out.append(_public_pdf_source(item))
        if len(out) >= 3:
            break
    return out


def execute_web_fallback(
    question: str,
    *,
    search_fn: Callable[[str], list[WebHit]] | None = None,
    generate_fn: Callable[[str], str] | None = None,
    generate: bool = True,
    document_answer: str | None = None,
) -> WebFallbackResult:
    provider = get_search_provider()
    try:
        hits = (search_fn or search_web)(question)
    except WebSearchError as exc:
        print(f"Web search error: {exc}")
        hits = []

    from config import WEB_MAX_SOURCES

    if WEB_MAX_SOURCES > 0:
        hits = hits[:WEB_MAX_SOURCES]
    if not hits:
        return WebFallbackResult(
            answer=WEB_UNAVAILABLE_ANSWER,
            sources=[],
            origin=ORIGIN_WEB_FALLBACK,
            reason="web_no_sources",
            provider=provider.name,
            preview=False,
        )

    sources = [hit_to_source(hit, index) for index, hit in enumerate(hits, start=1)]
    preview = all(hit.preview for hit in hits)
    document_text = str(document_answer or "").strip()
    miss_only = _document_miss_only(document_text)
    gap = bool(document_text) and not miss_only
    if preview:
        return WebFallbackResult(
            answer=WEB_GAP_PREVIEW_ANSWER if gap else WEB_PREVIEW_ANSWER,
            sources=sources,
            origin=ORIGIN_WEB_FALLBACK,
            reason="web_used",
            provider=provider.name,
            preview=True,
        )

    prompt = (
        build_web_gap_prompt(question, document_answer or "", hits)
        if gap
        else build_web_prompt(question, hits)
    )
    if not generate:
        return WebFallbackResult(
            answer="",
            sources=sources,
            origin=ORIGIN_WEB_FALLBACK,
            reason="web_used",
            provider=provider.name,
            preview=False,
            prompt=prompt,
        )

    if generate_fn is None:
        from llm_service import generate_response

        generate_fn = generate_response
    try:
        answer = finalize_web_answer(generate_fn(prompt))
    except Exception as exc:
        print(f"Web fallback: generation failed {type(exc).__name__}: {exc}", flush=True)
        answer = WEB_UNAVAILABLE_ANSWER
    return WebFallbackResult(
        answer=answer,
        sources=sources,
        origin=ORIGIN_WEB_FALLBACK,
        reason="web_used",
        provider=provider.name,
        preview=False,
        prompt=prompt,
    )


@dataclass
class AfterDocumentPass:
    action: str
    reason: str
    document_result: dict[str, Any]
    web_result: WebFallbackResult | None = None
    scope_note: str = ""

    @property
    def offer_web_fallback(self) -> bool:
        return self.reason == "web_skipped_toggle_off"

    @property
    def used_web(self) -> bool:
        return self.action == ACTION_WEB and self.web_result is not None


def resolve_after_document_pass(
    *,
    question: str,
    user_enabled: bool,
    document_result: dict[str, Any],
    search_fn: Callable[[str], list[WebHit]] | None = None,
    generate_fn: Callable[[str], str] | None = None,
    generate: bool = True,
    route: str = "/chat",
) -> AfterDocumentPass:
    action, reason = decide_web_fallback(
        user_enabled=user_enabled,
        document_result=document_result,
        question=question,
    )
    if action != ACTION_WEB:
        if reason != REASON_DOC_SUFFICIENT:
            log_web_decision(reason=reason, action=action, route=route)
        return AfterDocumentPass(
            action=action,
            reason=reason,
            document_result=document_result,
        )

    web_result = execute_web_fallback(
        question,
        search_fn=search_fn,
        generate_fn=generate_fn,
        generate=generate,
    )
    log_web_decision(
        reason=web_result.reason or reason,
        action=ACTION_WEB,
        hit_count=len(web_result.sources),
        provider=web_result.provider,
        route=route,
    )
    return AfterDocumentPass(
        action=ACTION_WEB,
        reason=web_result.reason or reason,
        document_result=document_result,
        web_result=web_result,
        scope_note="",
    )


def web_result_is_usable(web_result: WebFallbackResult | None) -> bool:
    if web_result is None:
        return False
    if not web_result.sources:
        return False
    if web_result.reason == "web_no_sources":
        return False
    return True


def resolve_after_document_answer(
    *,
    question: str,
    user_enabled: bool,
    answer: str,
    document_result: dict[str, Any] | None = None,
    search_fn: Callable[[str], list[WebHit]] | None = None,
    generate_fn: Callable[[str], str] | None = None,
    generate: bool = True,
    route: str = "/chat",
) -> WebFallbackResult | None:
    """If the finished document answer is a miss and Web is on, search."""
    should, reason = decide_web_after_answer(
        user_enabled=user_enabled,
        answer=answer,
        question=question,
        passages=passage_text_from_document(document_result),
    )
    print(
        f"Web fallback: post_llm search={should} reason={reason} "
        f"toggle={user_enabled}",
        flush=True,
    )
    if not should:
        if reason != REASON_DOC_SUFFICIENT:
            log_web_decision(reason=reason, action=ACTION_DOCUMENT, route=route)
        return None

    web_result = execute_web_fallback(
        question,
        search_fn=search_fn,
        generate_fn=generate_fn,
        generate=generate,
        document_answer=answer,
    )
    log_web_decision(
        reason=web_result.reason or reason,
        action=ACTION_WEB,
        hit_count=len(web_result.sources),
        provider=web_result.provider,
        route=route,
    )
    if not web_result_is_usable(web_result):
        return None
    return web_result


def document_chat_payload(
    document_result: dict[str, Any],
    *,
    offer_web_fallback: bool = False,
) -> dict[str, Any]:
    return {
        "answer": document_result.get("answer") or "",
        "sources": document_result.get("sources") or [],
        "answer_origin": ORIGIN_DOCUMENT,
        "web_sources": [],
        "offer_web_fallback": bool(offer_web_fallback),
    }


def web_chat_payload(web_result: WebFallbackResult) -> dict[str, Any]:
    return {
        "answer": web_result.answer,
        "sources": [],
        "answer_origin": web_result.origin,
        "web_sources": web_result.sources,
        "offer_web_fallback": False,
    }


def mixed_chat_payload(
    document_answer: str,
    document_sources: list[dict[str, Any]] | None,
    web_result: WebFallbackResult,
) -> dict[str, Any]:
    pdf = [
        item
        for item in (document_sources or [])
        if (item.get("kind") or "pdf") != "web"
        and (item.get("content_type") or "") != "web"
        and not item.get("url")
    ]
    return {
        "answer": combine_document_and_web_answer(document_answer, web_result.answer),
        "sources": pdf,
        "answer_origin": ORIGIN_MIXED,
        "web_sources": web_result.sources,
        "offer_web_fallback": False,
    }


__all__ = [
    "ACTION_CONTINUE",
    "ACTION_DOCUMENT",
    "ACTION_WEB",
    "AfterDocumentPass",
    "combine_document_and_web_answer",
    "decide_web_after_answer",
    "document_chat_payload",
    "document_sources_for_gap",
    "execute_web_fallback",
    "finalize_web_answer",
    "log_web_decision",
    "merge_answer_sources",
    "mixed_chat_payload",
    "resolve_after_document_answer",
    "resolve_after_document_pass",
    "search_web",
    "web_chat_payload",
    "web_result_is_usable",
]
