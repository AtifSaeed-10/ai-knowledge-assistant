"""Search providers. Live Tavily/Brave, plus mock and disabled."""

from __future__ import annotations

from datetime import datetime, timezone

from web_fallback.types import WebHit
from web_fallback.urls import clean_snippet, domain_from_url, is_public_http_url

PROVIDER_AUTO = "auto"
PROVIDER_MOCK = "mock"
PROVIDER_NONE = "none"
PROVIDER_TAVILY = "tavily"
PROVIDER_BRAVE = "brave"

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timeout() -> float:
    from config import WEB_SEARCH_TIMEOUT

    return max(3.0, float(WEB_SEARCH_TIMEOUT))


def _max_results() -> int:
    from config import WEB_SEARCH_RESULT_COUNT

    return max(3, int(WEB_SEARCH_RESULT_COUNT))


def _hit(
    *,
    title: str,
    url: str,
    snippet: str,
    provider: str,
    preview: bool,
    retrieved_at: str | None = None,
    tier: str = "unknown",
) -> WebHit | None:
    if not is_public_http_url(url):
        return None
    cleaned = clean_snippet(snippet)
    heading = clean_snippet(title, limit=180)
    if not heading and not cleaned:
        return None
    return WebHit(
        title=heading or domain_from_url(url) or "Web source",
        url=url.strip(),
        snippet=cleaned,
        domain=domain_from_url(url),
        provider=provider,
        preview=preview,
        retrieved_at=retrieved_at or _now(),
        tier=tier,
    )


def _snippet_with_date(snippet: str, published: str) -> str:
    text = (snippet or "").strip()
    date = (published or "").strip()
    if date and date.lower() not in text.lower():
        return f"{text} ({date})".strip()
    return text


class WebSearchProvider:
    name = PROVIDER_NONE

    def search(
        self,
        query: str,
        *,
        include_domains: list[str] | None = None,
        recency: bool = False,
    ) -> list[WebHit]:
        raise NotImplementedError


class DisabledWebSearchProvider(WebSearchProvider):
    """Fail closed: no hits, so the orchestrator will not invent facts."""

    name = PROVIDER_NONE

    def search(
        self,
        query: str,
        *,
        include_domains: list[str] | None = None,
        recency: bool = False,
    ) -> list[WebHit]:
        return []


class MockWebSearchProvider(WebSearchProvider):
    """
    Deterministic hits so the fallback path can be tested without a key.

    Snippets are labeled as preview text. They must never be treated as
    live IFAB / government facts.
    """

    name = PROVIDER_MOCK

    def search(
        self,
        query: str,
        *,
        include_domains: list[str] | None = None,
        recency: bool = False,
    ) -> list[WebHit]:
        text = (query or "").strip() or "this question"
        retrieved = _now()
        return [
            WebHit(
                title="Web lookup preview",
                url="https://example.com/docusage-web-preview",
                domain="example.com",
                snippet=(
                    "This is a development search result. Trusted-site lookup "
                    f"is not connected yet. The query was: {text}."
                ),
                provider=PROVIDER_MOCK,
                preview=True,
                retrieved_at=retrieved,
                tier="preview",
            ),
            WebHit(
                title="How fallback will work",
                url="https://example.org/docusage-trusted-sources",
                domain="example.org",
                snippet=(
                    "Later phases will restrict results to authentic domains "
                    "and quote only from fetched page text."
                ),
                provider=PROVIDER_MOCK,
                preview=True,
                retrieved_at=retrieved,
                tier="preview",
            ),
        ]


class TavilyWebSearchProvider(WebSearchProvider):
    name = PROVIDER_TAVILY

    def __init__(self, api_key: str):
        self._api_key = (api_key or "").strip()

    def search(
        self,
        query: str,
        *,
        include_domains: list[str] | None = None,
        recency: bool = False,
    ) -> list[WebHit]:
        from web_fallback.http import post_json

        body: dict = {
            "query": (query or "").strip(),
            "search_depth": "basic",
            "max_results": _max_results(),
            "include_answer": False,
            "include_raw_content": False,
        }
        if recency:
            body["topic"] = "news"
            body["days"] = 30
        if include_domains:
            body["include_domains"] = include_domains
        data = post_json(
            TAVILY_SEARCH_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            body=body,
            timeout=_timeout(),
            provider=self.name,
        )
        hits: list[WebHit] = []
        retrieved = _now()
        for row in data.get("results") or []:
            if not isinstance(row, dict):
                continue
            item = _hit(
                title=str(row.get("title") or ""),
                url=str(row.get("url") or ""),
                snippet=_snippet_with_date(
                    str(row.get("content") or row.get("snippet") or ""),
                    str(row.get("published_date") or row.get("published_at") or ""),
                ),
                provider=self.name,
                preview=False,
                retrieved_at=retrieved,
            )
            if item:
                hits.append(item)
        return hits


class BraveWebSearchProvider(WebSearchProvider):
    name = PROVIDER_BRAVE

    def __init__(self, api_key: str):
        self._api_key = (api_key or "").strip()

    def search(
        self,
        query: str,
        *,
        include_domains: list[str] | None = None,
        recency: bool = False,
    ) -> list[WebHit]:
        from web_fallback.http import get_json

        params: dict = {"q": (query or "").strip(), "count": _max_results()}
        if recency:
            params["freshness"] = "pm"
        data = get_json(
            BRAVE_SEARCH_URL,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self._api_key,
            },
            params=params,
            timeout=_timeout(),
            provider=self.name,
        )
        web = data.get("web") if isinstance(data.get("web"), dict) else {}
        rows = web.get("results") if isinstance(web, dict) else None
        hits: list[WebHit] = []
        retrieved = _now()
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            item = _hit(
                title=str(row.get("title") or ""),
                url=str(row.get("url") or ""),
                snippet=_snippet_with_date(
                    str(row.get("description") or row.get("snippet") or ""),
                    str(row.get("page_age") or row.get("age") or ""),
                ),
                provider=self.name,
                preview=False,
                retrieved_at=retrieved,
            )
            if item:
                hits.append(item)
        return hits


def _tavily_key() -> str:
    from config import TAVILY_API_KEY

    return (TAVILY_API_KEY or "").strip()


def _brave_key() -> str:
    from config import BRAVE_SEARCH_API_KEY

    return (BRAVE_SEARCH_API_KEY or "").strip()


def resolve_provider_name() -> str:
    from config import WEB_SEARCH_PROVIDER

    name = (WEB_SEARCH_PROVIDER or PROVIDER_AUTO).strip().lower()
    if name in {"off", "disabled"}:
        return PROVIDER_NONE
    if name in {"", PROVIDER_AUTO}:
        if _tavily_key():
            return PROVIDER_TAVILY
        if _brave_key():
            return PROVIDER_BRAVE
        return PROVIDER_MOCK
    return name


def get_search_provider() -> WebSearchProvider:
    name = resolve_provider_name()
    if name == PROVIDER_TAVILY:
        key = _tavily_key()
        if not key:
            return DisabledWebSearchProvider()
        return TavilyWebSearchProvider(key)
    if name == PROVIDER_BRAVE:
        key = _brave_key()
        if not key:
            return DisabledWebSearchProvider()
        return BraveWebSearchProvider(key)
    if name == PROVIDER_NONE:
        return DisabledWebSearchProvider()
    return MockWebSearchProvider()
