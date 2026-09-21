"""Turn web hits into citation dicts the API and the chat UI can store."""

from __future__ import annotations

from web_fallback.urls import WEB_SNIPPET_LIMIT, clean_snippet, domain_from_url
from web_fallback.types import WebHit


def hit_to_source(hit: WebHit, index: int) -> dict:
    evidence_id = f"W{index}"
    domain = hit.domain or domain_from_url(hit.url)
    title = hit.title.strip() or domain or "Web source"
    snippet = clean_snippet(hit.snippet or "", WEB_SNIPPET_LIMIT)
    return {
        "kind": "web",
        "evidence_id": evidence_id,
        "title": title,
        "filename": title,
        "url": hit.url,
        "domain": domain,
        "snippet": snippet,
        "quote": None,
        "provider": hit.provider,
        "preview": bool(hit.preview),
        "retrieved_at": hit.retrieved_at,
        "tier": hit.tier,
        "chunk_id": hit.url or evidence_id,
        "document_id": "",
        "page": None,
        "relevance": 100,
        "citation_eligible": False,
        "evidence_state": "page_only",
        "content_type": "web",
    }
