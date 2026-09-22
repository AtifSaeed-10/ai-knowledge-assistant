"""
Classify and rank web hits by authenticity.

Blocked domains never become evidence. Tier-1 and tier-2 are preferred.
Tier-3 / unknown hosts are used only when the trusted pool is too small.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
import re

import yaml

from web_fallback.coverage import content_tokens, web_query_tokens
from web_fallback.search_query import looks_like_recency_question
from web_fallback.urls import (
    canonical_source_key,
    domain_from_url,
    is_low_quality_wiki,
    is_non_english_wikipedia,
    looks_non_english,
    newest_year,
    tokens_close,
    wiki_list_boost,
)
from web_fallback.types import WebHit

TIER_T1 = "t1"
TIER_T2 = "t2"
TIER_T3 = "t3"
TIER_BLOCK = "block"
TIER_UNKNOWN = "unknown"

_DEFAULT_PATH = Path(__file__).resolve().parent / "domains.yaml"
_TIER_RANK = {
    TIER_T1: 0,
    TIER_T2: 1,
    TIER_T3: 2,
    TIER_UNKNOWN: 3,
    TIER_BLOCK: 99,
}


@dataclass(frozen=True)
class DomainPolicy:
    block: tuple[str, ...]
    t1_hosts: tuple[str, ...]
    t1_suffixes: tuple[str, ...]
    t2_hosts: tuple[str, ...]
    t2_suffixes: tuple[str, ...]

    def classify(self, host: str) -> str:
        domain = _normalize_host(host)
        if not domain:
            return TIER_UNKNOWN
        if _host_matches(domain, self.block):
            return TIER_BLOCK
        if _host_matches(domain, self.t1_hosts) or _suffix_matches(domain, self.t1_suffixes):
            return TIER_T1
        if _host_matches(domain, self.t2_hosts) or _suffix_matches(domain, self.t2_suffixes):
            return TIER_T2
        return TIER_UNKNOWN

    def trusted_hosts(self, limit: int = 40) -> list[str]:
        """Explicit T1 then T2 hosts for a provider include_domains filter."""
        out: list[str] = []
        seen: set[str] = set()
        for host in (*self.t1_hosts, *self.t2_hosts):
            if host in seen:
                continue
            seen.add(host)
            out.append(host)
            if len(out) >= max(1, limit):
                break
        return out


def _normalize_host(host: str) -> str:
    value = (host or "").strip().lower()
    if value.startswith("www."):
        value = value[4:]
    return value.rstrip(".")


def _host_matches(domain: str, hosts: Iterable[str]) -> bool:
    for host in hosts:
        if domain == host or domain.endswith("." + host):
            return True
    return False


def _suffix_matches(domain: str, suffixes: Iterable[str]) -> bool:
    for suffix in suffixes:
        token = suffix if suffix.startswith(".") else f".{suffix}"
        if domain.endswith(token) or domain == token.lstrip("."):
            return True
    return False


def _as_tuple(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    out: list[str] = []
    for item in raw:
        text = _normalize_host(str(item))
        if text:
            out.append(text)
    return tuple(out)


def load_domain_policy(path: str | Path | None = None) -> DomainPolicy:
    target = Path(path) if path else _policy_path()
    with target.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        data = {}
    tier1 = data.get("tier1") or {}
    tier2 = data.get("tier2") or {}
    return DomainPolicy(
        block=_as_tuple(data.get("block")),
        t1_hosts=_as_tuple(tier1.get("hosts") if isinstance(tier1, dict) else None),
        t1_suffixes=_as_tuple(tier1.get("suffixes") if isinstance(tier1, dict) else None),
        t2_hosts=_as_tuple(tier2.get("hosts") if isinstance(tier2, dict) else None),
        t2_suffixes=_as_tuple(tier2.get("suffixes") if isinstance(tier2, dict) else None),
    )


def _policy_path() -> Path:
    from config import WEB_DOMAINS_PATH

    if WEB_DOMAINS_PATH:
        return Path(WEB_DOMAINS_PATH)
    return _DEFAULT_PATH


@lru_cache(maxsize=4)
def get_domain_policy(path: str | None = None) -> DomainPolicy:
    return load_domain_policy(path)


def reset_domain_policy_cache() -> None:
    get_domain_policy.cache_clear()


def classify_url(url: str, policy: DomainPolicy | None = None) -> str:
    host = domain_from_url(url) or (urlparse(url).hostname or "")
    return (policy or get_domain_policy()).classify(host)


def annotate_hits(
    hits: Iterable[WebHit],
    policy: DomainPolicy | None = None,
) -> list[WebHit]:
    rules = policy or get_domain_policy()
    annotated: list[WebHit] = []
    for hit in hits:
        host = hit.domain or domain_from_url(hit.url)
        tier = rules.classify(host)
        annotated.append(
            replace(
                hit,
                domain=host or hit.domain,
                tier=tier,
            )
        )
    return annotated


def hit_relevance(question: str, hit: WebHit) -> float:
    asked = web_query_tokens(question)
    if not asked:
        asked = content_tokens(question)
    if not asked:
        return 1.0
    blob = f"{hit.title} {hit.url} {hit.snippet}"
    blob_tokens = set(re.findall(r"[a-z0-9]+", blob.lower()))
    matched = 0
    for token in asked:
        if token in blob_tokens or any(tokens_close(token, other) for other in blob_tokens):
            matched += 1
    return matched / len(asked)


def hit_year(hit: WebHit, today_year: int) -> int | None:
    return newest_year(hit.url, hit.title, hit.snippet, today_year=today_year)


def recency_rank(hit: WebHit, today_year: int) -> tuple[int, int]:
    """This-year dated pages first, then undated, then last year. Stale years are dropped earlier."""
    year = hit_year(hit, today_year)
    if year is None:
        return (1, 0)
    if year >= today_year:
        return (0, -year)
    return (2, -year)


def _min_hit_relevance(question: str, recency: bool) -> float:
    asked = web_query_tokens(question)
    if recency and len(asked) >= 3:
        return 0.6
    if recency:
        return 0.5
    return 0.34


def select_hits(
    hits: Iterable[WebHit],
    *,
    allow_t3: bool,
    limit: int,
    policy: DomainPolicy | None = None,
    question: str = "",
    today_year: int | None = None,
) -> list[WebHit]:
    """
    Drop blocked URLs, prefer T1 then T2, optionally keep T3/unknown.
    Dedupes by canonical URL. Drops Wikipedia talk/category pages.
    When a question is given, keeps pages that actually mention the ask.
    Recency questions drop stale dated pages instead of treating them as current.
    """
    from datetime import datetime, timezone

    allowed = {TIER_T1, TIER_T2}
    if allow_t3:
        allowed.update({TIER_T3, TIER_UNKNOWN})
    year_now = today_year or datetime.now(timezone.utc).year
    recency = bool(question) and looks_like_recency_question(question)

    ranked = []
    seen: set[str] = set()
    for hit in annotate_hits(hits, policy):
        host = hit.domain or domain_from_url(hit.url)
        if is_non_english_wikipedia(host):
            continue
        if is_low_quality_wiki(hit.url, hit.title):
            continue
        url_key = canonical_source_key(hit.url)
        if not url_key or url_key in seen:
            continue
        if hit.tier not in allowed:
            continue
        if not hit.snippet.strip() and not hit.title.strip():
            continue
        if question and hit_relevance(question, hit) < _min_hit_relevance(question, recency):
            continue
        if recency:
            dated = hit_year(hit, year_now)
            if dated is not None and dated < year_now - 1:
                continue
        seen.add(url_key)
        ranked.append(hit)

    ranked.sort(
        key=lambda item: (
            1 if looks_non_english(f"{item.title} {item.snippet}") else 0,
            *(recency_rank(item, year_now) if recency else (0, 0)),
            wiki_list_boost(item.url, item.title),
            -hit_relevance(question, item) if question else 0,
            _TIER_RANK.get(item.tier, 50),
            item.title.lower(),
        )
    )
    latin = [
        item
        for item in ranked
        if not looks_non_english(f"{item.title} {item.snippet}")
    ]
    if latin:
        ranked = latin
    cap = max(0, limit)
    return ranked[:cap] if cap else ranked
