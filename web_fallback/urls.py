"""URL helpers shared by search providers and the domain policy."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_TABLE_RE = re.compile(r"\s*\|\s*\|")
_HEADING_RE = re.compile(r"\s*#{1,6}\s+")
_NON_LATIN_RE = re.compile(
    r"[\u0400-\u04ff\u0600-\u06ff\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]"
)
_WIKI_SKIP_RE = re.compile(
    r"/wiki/(Talk:|Category(_talk)?:|User(_talk)?:|Wikipedia:|"
    r"Help:|Template:|Special:|File:|Portal:)",
    re.I,
)
_TITLE_SKIP_RE = re.compile(
    r"^(talk|category talk|user talk|wikipedia|help|template|portal)\s*:",
    re.I,
)
_EN_WIKI_SUBS = frozenset({"", "en", "simple", "www"})
WEB_SNIPPET_LIMIT = 180


def domain_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        return host[4:]
    return host


def is_public_http_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if not host or host in {"localhost", "127.0.0.1", "::1"}:
        return False
    if host.endswith(".local"):
        return False
    return True


def wikipedia_language(host: str) -> str | None:
    domain = (host or "").strip().lower()
    if domain.startswith("www."):
        domain = domain[4:]
    if not domain.endswith("wikipedia.org"):
        return None
    sub = domain[: -len("wikipedia.org")].rstrip(".")
    return sub


def is_non_english_wikipedia(host: str) -> bool:
    lang = wikipedia_language(host)
    if lang is None:
        return False
    return lang not in _EN_WIKI_SUBS


def canonical_source_key(url: str) -> str:
    """Fold language Wikipedia onto one article key so ja/en dupes collapse."""
    parsed = urlparse((url or "").strip())
    host = domain_from_url(url)
    path = unquote(parsed.path or "").rstrip("/").lower()
    if host.endswith("wikipedia.org"):
        return f"wikipedia.org{path}"
    return f"{host}{path}"


def is_low_quality_wiki(url: str, title: str = "") -> bool:
    path = unquote(urlparse((url or "").strip()).path or "")
    if _WIKI_SKIP_RE.search(path):
        return True
    heading = (title or "").strip()
    return bool(_TITLE_SKIP_RE.match(heading))


def wiki_list_boost(url: str, title: str = "") -> int:
    path = unquote(urlparse((url or "").strip()).path or "").lower()
    heading = (title or "").strip().lower()
    if "/wiki/list_of" in path or heading.startswith("list of "):
        return 0
    return 1


def edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    if abs(len(left) - len(right)) > 2:
        return 99
    prev = list(range(len(right) + 1))
    for i, a in enumerate(left, start=1):
        curr = [i]
        for j, b in enumerate(right, start=1):
            curr.append(
                min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (a != b))
            )
        prev = curr
    return prev[-1]


def tokens_close(left: str, right: str) -> bool:
    if left == right:
        return True
    if min(len(left), len(right)) < 5:
        return False
    return edit_distance(left, right) <= 1


_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def newest_year(*parts: str, today_year: int | None = None) -> int | None:
    """Newest 19xx/20xx year in titles, URLs, or snippets. None if undated."""
    blob = " ".join(parts)
    years = [int(token) for token in _YEAR_RE.findall(blob)]
    if not years:
        return None
    cap = today_year or datetime.now(timezone.utc).year
    plausible = [year for year in years if 1990 <= year <= cap + 1]
    return max(plausible) if plausible else None


def looks_non_english(text: str) -> bool:
    letters = [ch for ch in (text or "") if ch.isalpha()]
    if len(letters) < 12:
        return False
    foreign = sum(1 for ch in letters if _NON_LATIN_RE.match(ch))
    return foreign * 5 >= len(letters)


def clean_snippet(text: str, limit: int = WEB_SNIPPET_LIMIT) -> str:
    value = html.unescape(_TAG_RE.sub(" ", text or ""))
    value = re.sub(r"^\s*title:\s*", "", value, flags=re.I)
    value = re.sub(r"\s*\d+\.\s*↑.*$", " ", value)
    value = _SPACE_RE.sub(" ", value).strip()
    prose = _TABLE_RE.split(value, maxsplit=1)[0]
    prose = _HEADING_RE.split(prose, maxsplit=1)[0].strip()
    if len(prose) >= 40:
        value = prose
    if limit > 0 and len(value) > limit:
        return value[: limit - 1].rstrip() + "…"
    return value
