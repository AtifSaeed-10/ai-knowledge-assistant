"""
RAG V2 Phase 2+3 — hybrid retrieval + cross-encoder reranking.

Pipeline:

    retrieve_dense() ─┐
                      ├─→ fuse_results() → dedupe → RERANK_CANDIDATE_K
    retrieve_bm25()  ─┘              ↓
                              query-type reserved slots (phrase / front-matter)
                                     ↓
                              BGE reranker
                                     ↓
                              recall pool (RECALL_TOP_K)
                              citation pool = recall ∩ CITATION_MIN_RELEVANCE

Public shape matches legacy retrieve_chunks, plus separated score fields:
{chunks, distances, metadata, ids, dense_distances, bm25_scores,
 rrf_scores, reranker_scores, relevances, rerank_fallback,
 citation_eligible, recall_fallbacks, recall_fallback, fused_count}
"""

from __future__ import annotations

from typing import Any

from config import (
    CANDIDATE_K,
    RECALL_TOP_K,
    RERANK_CANDIDATE_K,
    RRF_K,
    TOP_K,
)
from bm25_index import bm25_index
from index_hygiene import chroma_where_for_document_ids, filter_hits_to_documents
from query_retrieval import (
    RetrievalQuery,
    classify_retrieval_query,
    ensure_typed_hits_in_pool,
)
from reranker import (
    RerankerUnavailableError,
    rerank_candidates,
    rrf_fallback_candidates,
)
from rerank_calibration import (
    pre_llm_rank_diagnostics,
    zero_result_when_fused,
)


def _empty_chroma_result() -> dict:
    return {
        "ids": [[]],
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }


def retrieve_dense(
    question: str,
    *,
    collection,
    embedding_model,
    document_ids: list[str] | None = None,
    k: int | None = None,
) -> list[dict[str, Any]]:
    """
    Dense vector retrieval from Chroma.

    Returns candidate dicts:
    {id, text, metadata, dense_distance, rank}
    """
    candidate_k = k if k is not None else CANDIDATE_K
    if candidate_k <= 0:
        return []
    if document_ids is not None and len(document_ids) == 0:
        return []

    count = collection.count()
    if count == 0:
        return []

    n_results = min(candidate_k, count)
    question_embedding = list(embedding_model.embed([question]))[0]
    where = chroma_where_for_document_ids(document_ids)

    query_kwargs: dict[str, Any] = {
        "query_embeddings": [question_embedding],
        "n_results": n_results,
    }
    if where is not None:
        query_kwargs["where"] = where

    try:
        results = collection.query(**query_kwargs)
    except Exception:
        # Filtered subsets can be smaller than n_results on some Chroma versions.
        if n_results <= 1:
            results = _empty_chroma_result()
        else:
            query_kwargs["n_results"] = max(1, n_results // 2)
            try:
                results = collection.query(**query_kwargs)
            except Exception:
                results = _empty_chroma_result()

    ids = (results.get("ids") or [[]])[0] or []
    documents = (results.get("documents") or [[]])[0] or []
    metadatas = (results.get("metadatas") or [[]])[0] or []
    distances = (results.get("distances") or [[]])[0] or []

    hits: list[dict[str, Any]] = []
    for rank, chunk_id in enumerate(ids, start=1):
        hits.append(
            {
                "id": chunk_id,
                "text": documents[rank - 1] if rank - 1 < len(documents) else "",
                "metadata": metadatas[rank - 1] if rank - 1 < len(metadatas) else {},
                "dense_distance": (
                    float(distances[rank - 1])
                    if rank - 1 < len(distances)
                    else None
                ),
                "rank": rank,
            }
        )
    return filter_hits_to_documents(hits, document_ids)


def retrieve_bm25(
    question: str,
    *,
    collection,
    document_ids: list[str] | None = None,
    k: int | None = None,
    phrases: list[str] | None = None,
    page_min: int | None = None,
    page_max: int | None = None,
) -> list[dict[str, Any]]:
    """
    BM25 lexical retrieval over the Chroma-backed in-memory index.
    """
    candidate_k = k if k is not None else CANDIDATE_K
    if document_ids is not None and len(document_ids) == 0:
        return []
    bm25_index.ensure_loaded(collection)
    return bm25_index.search(
        question,
        candidate_k,
        document_ids=document_ids,
        phrases=phrases,
        page_min=page_min,
        page_max=page_max,
    )


def fuse_results(
    dense_hits: list[dict[str, Any]],
    bm25_hits: list[dict[str, Any]],
    *,
    rrf_k: int | None = None,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """
    Reciprocal Rank Fusion with dedupe by chunk id.

    score(d) = Σ 1 / (rrf_k + rank_i(d)) over ranked lists containing d.

    Returns up to top_k fused candidates with separated score fields.
    Does NOT invent a Chroma-compatible distance for reranking.
    """
    constant = rrf_k if rrf_k is not None else RRF_K
    limit = top_k if top_k is not None else RERANK_CANDIDATE_K

    fused: dict[str, dict[str, Any]] = {}

    def _accumulate(hits: list[dict[str, Any]], source: str) -> None:
        for hit in hits:
            chunk_id = hit["id"]
            rank = int(hit.get("rank") or 0)
            if rank <= 0:
                continue
            entry = fused.get(chunk_id)
            if entry is None:
                entry = {
                    "id": chunk_id,
                    "text": hit.get("text") or "",
                    "metadata": hit.get("metadata") or {},
                    "dense_distance": hit.get("dense_distance"),
                    "bm25_score": hit.get("bm25_score"),
                    "rrf_score": 0.0,
                    "sources": set(),
                }
                fused[chunk_id] = entry
            else:
                if not entry["text"] and hit.get("text"):
                    entry["text"] = hit["text"]
                if not entry["metadata"] and hit.get("metadata"):
                    entry["metadata"] = hit["metadata"]
                if entry.get("dense_distance") is None and hit.get("dense_distance") is not None:
                    entry["dense_distance"] = hit["dense_distance"]
                if entry.get("bm25_score") is None and hit.get("bm25_score") is not None:
                    entry["bm25_score"] = hit["bm25_score"]

            entry["rrf_score"] += 1.0 / (constant + rank)
            entry["sources"].add(source)

    _accumulate(dense_hits, "dense")
    _accumulate(bm25_hits, "bm25")

    ranked = sorted(
        fused.values(),
        key=lambda item: (-item["rrf_score"], item["id"]),
    )

    results: list[dict[str, Any]] = []
    for item in ranked[:limit]:
        results.append(
            {
                "id": item["id"],
                "text": item["text"],
                "metadata": item["metadata"],
                "dense_distance": item.get("dense_distance"),
                "bm25_score": item.get("bm25_score"),
                "rrf_score": float(item["rrf_score"]),
                "sources": sorted(item["sources"]),
            }
        )
    return results


def _legacy_distance(item: dict[str, Any]) -> float | None:
    """
    Logger-compatible distance field: dense distance only when present.
    Never substitutes reranker scores.
    """
    dense = item.get("dense_distance")
    return float(dense) if dense is not None else None


def _empty_retrieval_result(*, fused_count: int = 0) -> dict[str, Any]:
    return {
        "chunks": [],
        "distances": [],
        "metadata": [],
        "ids": [],
        "dense_distances": [],
        "bm25_scores": [],
        "rrf_scores": [],
        "reranker_scores": [],
        "relevances": [],
        "citation_eligible": [],
        "recall_fallbacks": [],
        "recall_fallback": False,
        "fused_count": fused_count,
        "rerank_fallback": False,
        "rerank_input_count": fused_count,
        "rerank_unique_count": fused_count,
        "rerank_deduped_count": 0,
        "rank1_id": None,
        "rank1_page": None,
        "retrieval_pages": [],
        "score_gap_12": None,
        "gating_path": None,
        "zero_result": False,
        "query_kind": "default",
        "query_phrases": [],
    }


def _pack_retrieval_result(
    selected: list[dict[str, Any]],
    *,
    fused_count: int,
    rerank_fallback: bool,
    rerank_stats: dict[str, Any],
    query_profile: RetrievalQuery | None = None,
) -> dict[str, Any]:
    recall_flags = [bool(item.get("recall_fallback")) for item in selected]
    diagnostics = pre_llm_rank_diagnostics(selected)
    return {
        "chunks": [item["text"] for item in selected],
        # Legacy field: dense distance only (never reranker score).
        "distances": [_legacy_distance(item) for item in selected],
        "metadata": [item["metadata"] for item in selected],
        "ids": [item["id"] for item in selected],
        "dense_distances": [item.get("dense_distance") for item in selected],
        "bm25_scores": [item.get("bm25_score") for item in selected],
        "rrf_scores": [item.get("rrf_score") for item in selected],
        "reranker_scores": [item.get("reranker_score") for item in selected],
        "relevances": [item.get("relevance") for item in selected],
        "citation_eligible": [
            bool(item.get("citation_eligible")) for item in selected
        ],
        "recall_fallbacks": recall_flags,
        "recall_fallback": any(recall_flags),
        "fused_count": fused_count,
        "rerank_fallback": rerank_fallback,
        "rerank_input_count": rerank_stats.get("input_count"),
        "rerank_unique_count": rerank_stats.get("unique_count"),
        "rerank_deduped_count": rerank_stats.get("deduped_count"),
        "rank1_id": diagnostics["rank1_id"],
        "rank1_page": diagnostics["rank1_page"],
        "retrieval_pages": diagnostics["retrieval_pages"],
        "score_gap_12": diagnostics["score_gap_12"],
        "gating_path": rerank_stats.get("gating_path")
        or diagnostics.get("gating_path"),
        "zero_result": zero_result_when_fused(fused_count, len(selected)),
        "query_kind": (query_profile.kind if query_profile else "default"),
        "query_phrases": list(query_profile.phrases) if query_profile else [],
    }


def _collect_typed_hits(
    question: str,
    profile: RetrievalQuery,
    *,
    collection,
    document_ids: list[str] | None,
    k: int,
) -> list[dict[str, Any]]:
    """Extra BM25 probes for structured query types (does not replace hybrid)."""
    if profile.kind == "default" and not profile.extra_queries:
        return []

    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    queries = list(profile.extra_queries)
    if profile.page_max is not None:
        queries.append(question)
    if not queries:
        return []

    for probe in queries:
        batch = retrieve_bm25(
            probe,
            collection=collection,
            document_ids=document_ids,
            k=k,
            phrases=profile.phrases or None,
            page_min=profile.page_min,
            page_max=profile.page_max,
        )
        for hit in batch:
            chunk_id = hit.get("id")
            if not chunk_id or chunk_id in seen:
                continue
            seen.add(chunk_id)
            hits.append(hit)
    return hits


def retrieve_candidates(
    question: str,
    *,
    collection,
    embedding_model,
    document_ids: list[str] | None = None,
    candidate_k: int | None = None,
    rerank_candidate_k: int | None = None,
    top_k: int | None = None,
    rrf_k: int | None = None,
    retrieval_query: RetrievalQuery | None = None,
) -> dict[str, Any]:
    """
    Hybrid + rerank entrypoint.

    Dense + BM25 → RRF (deduped pool) → query-type reserved slots →
    cross-encoder rerank → recall pool.
    """
    profile = retrieval_query or classify_retrieval_query(question)
    k = candidate_k if candidate_k is not None else CANDIDATE_K
    k = k + int(profile.candidate_k_boost or 0)
    pool_k = (
        rerank_candidate_k
        if rerank_candidate_k is not None
        else RERANK_CANDIDATE_K
    )
    final_k = top_k if top_k is not None else RECALL_TOP_K
    if final_k is None:
        final_k = TOP_K
    if document_ids is not None and len(document_ids) == 0:
        return _empty_retrieval_result()

    dense_hits = retrieve_dense(
        question,
        collection=collection,
        embedding_model=embedding_model,
        document_ids=document_ids,
        k=k,
    )
    bm25_hits = retrieve_bm25(
        question,
        collection=collection,
        document_ids=document_ids,
        k=k,
        phrases=profile.phrases or None,
    )
    fused = fuse_results(
        dense_hits,
        bm25_hits,
        rrf_k=rrf_k,
        top_k=pool_k,
    )
    typed_hits = _collect_typed_hits(
        question,
        profile,
        collection=collection,
        document_ids=document_ids,
        k=k,
    )
    fused = ensure_typed_hits_in_pool(
        fused,
        typed_hits,
        reserved=int(profile.reserved_slots or 0),
        limit=pool_k,
    )

    print("\n========== HYBRID RETRIEVAL ==========")
    print("Question:", question)
    print("Document IDs:", document_ids)
    print(
        f"Query type: {profile.kind} phrases={profile.phrases[:6]} "
        f"page_max={profile.page_max}"
    )
    print(f"Dense hits: {len(dense_hits)} | BM25 hits: {len(bm25_hits)}")
    print(
        f"Fused pool (<={pool_k}): {len(fused)} "
        f"(typed extra {len(typed_hits)})"
    )

    fallback = False
    rerank_stats: dict[str, Any] = {
        "input_count": len(fused),
        "unique_count": len(fused),
        "deduped_count": 0,
    }
    try:
        selected = rerank_candidates(
            question,
            fused,
            top_k=final_k,
            stats_out=rerank_stats,
        )
        print("\n========== RERANK ==========")
        print(
            f"Entering BGE: {rerank_stats.get('unique_count')} "
            f"(from {rerank_stats.get('input_count')}, "
            f"exact-text deduped {rerank_stats.get('deduped_count')})"
        )
        fallback_note = ""
        if any(item.get("recall_fallback") for item in selected):
            fallback_note = " [recall-first: kept slots below evidence floor]"
        print(f"Model pool -> top {final_k}: {len(selected)}{fallback_note}")
        for item in selected:
            print(
                f"  {item['id']} rerank={item['reranker_score']:.4f} "
                f"rel={item['relevance']} rrf={item['rrf_score']:.4f} "
                f"dense={item['dense_distance']} bm25={item['bm25_score']}"
            )
    except RerankerUnavailableError as exc:
        fallback = True
        selected = rrf_fallback_candidates(
            fused,
            top_k=final_k,
            reason=str(exc),
        )
        print("\n========== RERANK FALLBACK (RRF) ==========")
        for item in selected:
            print(
                f"  {item['id']} rrf={item['rrf_score']:.4f} "
                f"rel={item['relevance']}"
            )

    if fused and not selected:
        print(
            "WARNING: recall-first safety net: nonempty fused pool "
            "produced 0 rerank slots"
        )
        selected = rrf_fallback_candidates(
            fused,
            top_k=final_k,
            reason="nonempty fused pool produced 0 rerank slots",
        )

    diagnostics = pre_llm_rank_diagnostics(selected)
    print(
        "Pre-LLM: "
        f"rank1_page={diagnostics['rank1_page']} "
        f"gap12={diagnostics['score_gap_12']} "
        f"gating={diagnostics['gating_path']} "
        f"zero_result={zero_result_when_fused(len(fused), len(selected))}"
    )

    return _pack_retrieval_result(
        selected,
        fused_count=len(fused),
        rerank_fallback=fallback,
        rerank_stats=rerank_stats,
        query_profile=profile,
    )
