"""
BM25 lexical index over the same Chroma corpus used for dense retrieval.

The index is built from Chroma documents/ids/metadatas so BM25 and dense
retrieval never diverge onto separate corpora. An in-memory BM25Okapi is
cached and rebuilt only when the Chroma fingerprint changes.
"""

from __future__ import annotations

import hashlib
import re
import threading
from typing import Any

from rank_bm25 import BM25Okapi

from config import PHRASE_BM25_BOOST


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Deterministic lowercase alphanumeric tokenizer."""
    if not text:
        return []
    return _TOKEN_RE.findall(text.lower())


def contains_consecutive_phrase(
    document_tokens: list[str],
    phrase: str,
) -> bool:
    """True when phrase tokens appear as a contiguous span in document_tokens."""
    needle = tokenize(phrase)
    if not needle:
        return False
    hay = document_tokens
    n = len(needle)
    if n == 1:
        return needle[0] in hay
    if len(hay) < n:
        return False
    for i in range(len(hay) - n + 1):
        if hay[i : i + n] == needle:
            return True
    return False


def metadata_page(metadata: dict | None) -> int | None:
    if not metadata:
        return None
    value = metadata.get("page_number")
    if value is None:
        value = metadata.get("page_start")
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    if page < 1:
        return None
    return page


def corpus_fingerprint(ids: list[str]) -> str:
    """Stable fingerprint of the indexed chunk ID set."""
    joined = "\n".join(sorted(ids))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


class BM25Index:
    """Thread-safe BM25 index mirrored from a Chroma collection."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._bm25: BM25Okapi | None = None
        self._ids: list[str] = []
        self._documents: list[str] = []
        self._metadatas: list[dict[str, Any]] = []
        self._fingerprint: str | None = None

    @property
    def size(self) -> int:
        return len(self._ids)

    @property
    def fingerprint(self) -> str | None:
        return self._fingerprint

    def invalidate(self) -> None:
        """Force rebuild on next ensure_loaded()."""
        with self._lock:
            self._bm25 = None
            self._ids = []
            self._documents = []
            self._metadatas = []
            self._fingerprint = None

    def ensure_loaded(self, collection) -> None:
        """
        Load/rebuild from Chroma when empty or when the corpus fingerprint
        no longer matches the live collection.
        """
        with self._lock:
            live = collection.get(include=["documents", "metadatas"])
            ids = list(live.get("ids") or [])
            documents = list(live.get("documents") or [])
            metadatas = list(live.get("metadatas") or [])

            # Chroma may return None entries; normalize.
            normalized_docs: list[str] = []
            normalized_metas: list[dict[str, Any]] = []
            normalized_ids: list[str] = []
            for i, chunk_id in enumerate(ids):
                doc = documents[i] if i < len(documents) else None
                meta = metadatas[i] if i < len(metadatas) else None
                if doc is None:
                    continue
                normalized_ids.append(chunk_id)
                normalized_docs.append(doc)
                normalized_metas.append(meta or {})

            fp = corpus_fingerprint(normalized_ids)
            if (
                self._bm25 is not None
                and self._fingerprint == fp
                and len(self._ids) == len(normalized_ids)
            ):
                return

            if not normalized_ids:
                self._bm25 = None
                self._ids = []
                self._documents = []
                self._metadatas = []
                self._fingerprint = fp
                return

            tokenized = [tokenize(doc) for doc in normalized_docs]
            # BM25Okapi requires non-empty corpus; empty token docs become [""]
            tokenized = [toks if toks else [""] for toks in tokenized]
            self._bm25 = BM25Okapi(tokenized)
            self._ids = normalized_ids
            self._documents = normalized_docs
            self._metadatas = normalized_metas
            self._fingerprint = fp

    def corpus_texts(self, document_ids: list[str] | None = None) -> list[str]:
        """Indexed passage text, optionally narrowed to some documents."""
        with self._lock:
            if not self._documents:
                return []
            if document_ids is None:
                return list(self._documents)
            allowed = set(document_ids)
            if not allowed:
                return []
            return [
                text
                for i, text in enumerate(self._documents)
                if self._metadatas[i].get("document_id") in allowed
            ]

    def search(
        self,
        query: str,
        k: int,
        document_ids: list[str] | None = None,
        *,
        phrases: list[str] | None = None,
        page_min: int | None = None,
        page_max: int | None = None,
        phrase_boost: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return top-k BM25 hits as candidate dicts:
        {id, text, metadata, bm25_score, rank}

        Optional consecutive-phrase boost multiplies a hit's score when any
        phrase appears as a contiguous token span. Page min/max filter on
        stored chunk metadata without changing the BM25 model.
        """
        with self._lock:
            if self._bm25 is None or not self._ids or k <= 0:
                return []

            tokens = tokenize(query)
            if not tokens:
                return []

            scores = list(self._bm25.get_scores(tokens))
            boost = (
                PHRASE_BM25_BOOST if phrase_boost is None else float(phrase_boost)
            )
            phrase_list = [p for p in (phrases or []) if p and tokenize(p)]
            allowed = None
            if document_ids is not None:
                if not document_ids:
                    return []
                allowed = set(document_ids)

            ranked: list[tuple[float, int]] = []
            for i, raw_score in enumerate(scores):
                if allowed is not None:
                    doc_id = self._metadatas[i].get("document_id")
                    if doc_id not in allowed:
                        continue
                if page_min is not None or page_max is not None:
                    page = metadata_page(self._metadatas[i])
                    if page is None:
                        continue
                    if page_min is not None and page < page_min:
                        continue
                    if page_max is not None and page > page_max:
                        continue
                score = float(raw_score)
                if phrase_list:
                    doc_tokens = tokenize(self._documents[i])
                    matched = any(
                        contains_consecutive_phrase(doc_tokens, phrase)
                        for phrase in phrase_list
                    )
                    if matched:
                        if score <= 0:
                            score = 1.0
                        score *= boost
                ranked.append((score, i))

            # Deterministic: score desc, then id asc for ties.
            ranked.sort(
                key=lambda item: (-item[0], self._ids[item[1]])
            )

            hits: list[dict[str, Any]] = []
            for rank, (score, idx) in enumerate(ranked[:k], start=1):
                # Skip zero/negative scores unless everything is zero — still
                # allow weakly positive lexical matches only.
                if score <= 0:
                    continue
                hits.append(
                    {
                        "id": self._ids[idx],
                        "text": self._documents[idx],
                        "metadata": self._metadatas[idx],
                        "bm25_score": score,
                        "rank": rank,
                    }
                )
            return hits


# Process-wide singleton shared by retrieval.
bm25_index = BM25Index()
