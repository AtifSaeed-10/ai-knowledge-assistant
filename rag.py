import chromadb
from fastembed import TextEmbedding

from llm_service import generate_response
from retrieval_logger import log_retrieval
from query_rewriter import rewrite_query
from conversation_query import analyze_turn, infer_subject_phrase
from answer_prompt import build_answer_prompt
from answer_planner import format_plan_for_prompt, plan_answer
from evidence_focus import citation_allowlist, format_evidence_notes
from modes import normalize_mode
from config import (
    CHROMA_DB_PATH,
    COLLECTION_NAME,
    TOP_K,
    CANDIDATE_K,
    RERANK_CANDIDATE_K,
    RERANK_TOP_K,
    RRF_K,
    CITATION_MIN_RELEVANCE,
)
from bm25_index import bm25_index
from reranker import reranker
from citation_resolver import evidence_id_for_index, resolve_answer
from claim_validator import finalize_answer_citations, used_sources
from evidence_mapping import make_snippet
from hybrid_retrieval import (
    retrieve_dense,
    retrieve_bm25,
    fuse_results,
    retrieve_candidates as hybrid_retrieve_candidates,
)


def _dedupe_sources(sources: list[dict]) -> list[dict]:
    """Keep one citation per chunk; preserve retrieval order."""
    seen: set[str] = set()
    unique: list[dict] = []
    for source in sources:
        key = str(source.get("chunk_id") or "")
        if not key:
            key = f"{source.get('document_id') or ''}:{source.get('page')}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)
    return unique


def _build_citation_sources(
    chunks: list,
    ids: list,
    metadata: list,
    relevances: list,
    search_query: str,
    analysis,
) -> tuple[list[dict], list[str | None]]:
    """
    Assign stable E1..En ids to citeable retrieved chunks in retrieval order.
    Distinct chunks on the same page keep separate ids.
    """
    allowed_citations = citation_allowlist(chunks, search_query, analysis)
    sources: list[dict] = []
    evidence_ids: list[str | None] = [None] * len(chunks)
    seen_chunk_ids: set[str] = set()

    for idx, (chunk_id, meta) in enumerate(zip(ids, metadata)):
        if idx < len(relevances) and relevances[idx] is not None:
            relevance = int(relevances[idx])
        else:
            relevance = 0
        relevance = max(0, min(100, relevance))

        if relevance < CITATION_MIN_RELEVANCE:
            continue
        if allowed_citations is not None and idx not in allowed_citations:
            continue
        if chunk_id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(chunk_id)

        meta = meta or {}
        page = _citation_page(meta)
        evidence_id = evidence_id_for_index(len(sources) + 1)
        evidence_ids[idx] = evidence_id
        chunk_text = chunks[idx] if idx < len(chunks) else ""
        sources.append(
            {
                "document_id": meta.get("document_id") or "",
                "filename": meta.get("filename") or "",
                "page": page,
                "chunk_id": chunk_id,
                "relevance": relevance,
                "evidence_id": evidence_id,
                "snippet": make_snippet(
                    chunk_text if isinstance(chunk_text, str) else ""
                ),
                "quote": None,
            }
        )

    return _dedupe_sources(sources), evidence_ids


def _citation_page(meta: dict) -> int | None:
    """
    Use stored chunk page metadata only. Never invent a page number.
    Invalid / missing values become None so the viewer can fail gracefully.
    """
    if not meta:
        return None
    value = meta.get("page_number")
    if value is None:
        value = meta.get("page_start")
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    if page < 1:
        return None
    return page


# ========================
# Chroma Client
# ========================

client = chromadb.PersistentClient(
    path=CHROMA_DB_PATH
)


def get_collection():

    return client.get_or_create_collection(
        name=COLLECTION_NAME
    )


# ========================
# Embedding Model
# ========================

model = TextEmbedding(
    model_name="BAAI/bge-small-en-v1.5"
)


# ========================
# Hybrid + Rerank Retrieval (Phase 2 + 3)
# ========================
# Dense + BM25 → RRF pool → BGE reranker → TOP_K evidence.


def retrieve_candidates(
    question,
    document_ids=None,
    candidate_k=None,
    rerank_candidate_k=None,
    top_k=None,
):
    """
    Hybrid + rerank candidate retrieval.

    Returns legacy keys plus separated score lists.
    """
    return hybrid_retrieve_candidates(
        question,
        collection=get_collection(),
        embedding_model=model,
        document_ids=document_ids,
        candidate_k=candidate_k if candidate_k is not None else CANDIDATE_K,
        rerank_candidate_k=(
            rerank_candidate_k
            if rerank_candidate_k is not None
            else RERANK_CANDIDATE_K
        ),
        top_k=top_k if top_k is not None else RERANK_TOP_K,
        rrf_k=RRF_K,
    )


def retrieve_chunks(
    question,
    document_ids=None
):
    """
    Public retrieval API (unchanged contract).

    Phase 3: hybrid fusion + cross-encoder reranking.
    """
    return retrieve_candidates(
        question,
        document_ids=document_ids,
    )


# Re-export building blocks for tests / later phases.
__all__ = [
    "ask_question",
    "get_collection",
    "retrieve_chunks",
    "retrieve_candidates",
    "retrieve_dense",
    "retrieve_bm25",
    "fuse_results",
    "bm25_index",
    "reranker",
]


def _merge_retrieval_results(
    primary: dict,
    supplemental: dict,
    *,
    max_extra: int = 2,
) -> dict:
    """
    Append unique chunks from a supplemental retrieval pass.

    Keeps primary rerank order; adds up to max_extra new chunks at the end.
    """
    if max_extra <= 0 or not supplemental.get("ids"):
        return primary

    seen = set(primary.get("ids") or [])
    merged = {key: list(primary.get(key) or []) for key in (
        "chunks",
        "distances",
        "metadata",
        "ids",
        "dense_distances",
        "bm25_scores",
        "rrf_scores",
        "reranker_scores",
        "relevances",
    )}
    added = 0
    for idx, chunk_id in enumerate(supplemental.get("ids") or []):
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        merged["chunks"].append(supplemental["chunks"][idx])
        for field in (
            "distances",
            "metadata",
            "ids",
            "dense_distances",
            "bm25_scores",
            "rrf_scores",
            "reranker_scores",
            "relevances",
        ):
            values = supplemental.get(field) or []
            merged[field].append(values[idx] if idx < len(values) else None)
        added += 1
        if added >= max_extra:
            break

    if added == 0:
        return primary

    out = dict(primary)
    for field, values in merged.items():
        out[field] = values
    return out


def _retrieve_with_plan(
    search_query: str,
    plan,
    document_ids=None,
) -> dict:
    """Primary hybrid retrieval, optionally augmented by plan sub-queries."""
    primary = retrieve_candidates(search_query, document_ids)
    sub_queries = [
        item.strip()
        for item in (getattr(plan, "sub_queries", None) or [])
        if item and item.strip()
    ]
    if not sub_queries:
        return primary

    normalized_primary = search_query.strip().lower()
    result = primary
    extras_budget = 2
    for sub_query in sub_queries[:3]:
        if extras_budget <= 0:
            break
        if sub_query.strip().lower() == normalized_primary:
            continue
        supplemental = retrieve_candidates(
            sub_query,
            document_ids,
            top_k=2,
        )
        before = len(result.get("ids") or [])
        result = _merge_retrieval_results(
            result,
            supplemental,
            max_extra=extras_budget,
        )
        extras_budget -= max(0, len(result.get("ids") or []) - before)
    return result


def ask_question(
    question: str,
    history=None,
    document_ids=None,
    *,
    generate: bool = True,
    mode: str | None = None,
):
    """
    Run retrieval/rerank, build prompt + citations, optionally generate.

    generate=True  → non-streaming /chat (default; full answer)
    generate=False → /chat/stream prepares prompt once; caller streams LLM
    """

    product_mode = normalize_mode(mode)

    # ------------------------
    # Conversational query understanding
    # ------------------------

    analysis = analyze_turn(question, history)
    search_query = question
    if history and analysis.needs_rewrite:
        rewritten = rewrite_query(
            question,
            history,
            analysis=analysis,
        )
        if rewritten and str(rewritten).strip():
            search_query = str(rewritten).strip()


    print("\n========== SEARCH QUERY ==========")
    print(search_query)
    print(
        f"Turn: intent={analysis.intent} relation={analysis.relation} "
        f"rewrite={analysis.needs_rewrite} ({analysis.reason})"
    )

    answer_plan_obj = plan_answer(question, search_query, analysis)

    retrieval_result = _retrieve_with_plan(
        search_query,
        answer_plan_obj,
        document_ids,
    )


    chunks = retrieval_result["chunks"]
    distances = retrieval_result["distances"]
    metadata = retrieval_result["metadata"]
    ids = retrieval_result["ids"]
    relevances = retrieval_result.get("relevances") or []
    reranker_scores = retrieval_result.get("reranker_scores") or []
    rerank_fallback = bool(retrieval_result.get("rerank_fallback"))


    # ------------------------
    # Log Retrieval
    # ------------------------

    log_retrieval(
        search_query,
        chunks,
        distances,
        ids,
        metadata
                )


    if not chunks:

        return {
            "answer": "No relevant information found in the document.",
            "sources": [],
            "prompt": None,
        }


    # Final evidence is already rerank-selected (or explicit RRF fallback).
    # Do NOT apply SIMILARITY_THRESHOLD to reranker scores / pseudo-distances.


    # ------------------------
    # Debug Output
    # ------------------------

    print("\n========== RETRIEVED CHUNKS ==========\n")
    if rerank_fallback:
        print("(reranker unavailable — using RRF fallback order)\n")


    for i, chunk in enumerate(chunks, start=1):
        dense = distances[i - 1] if i - 1 < len(distances) else None
        rr = reranker_scores[i - 1] if i - 1 < len(reranker_scores) else None
        rel = relevances[i - 1] if i - 1 < len(relevances) else None
        print(f"Chunk {i}")
        print(f"Dense distance: {dense}")
        print(f"Reranker score: {rr}")
        print(f"Relevance: {rel}")
        print("-" * 50)
        print(chunk[:500])
        print()



    # ------------------------
    # Citations (E-ids) then prompt
    # ------------------------

    sources, evidence_ids = _build_citation_sources(
        chunks,
        ids,
        metadata,
        relevances,
        search_query,
        analysis,
    )

    subject = analysis.subject or infer_subject_phrase(search_query)
    evidence_notes = format_evidence_notes(
        chunks,
        metadata,
        search_query,
        analysis,
    )
    plan_text = format_plan_for_prompt(answer_plan_obj)

    prompt = build_answer_prompt(
        question=question,
        search_query=search_query,
        history=history,
        chunks=chunks,
        metadata=metadata,
        ids=ids,
        evidence_ids=evidence_ids,
        relevances=relevances,
        analysis=analysis,
        mode=product_mode,
        evidence_notes=evidence_notes,
        subject=subject,
        answer_plan=plan_text,
    )


    print("\n========== PROMPT SENT TO LLM ==========\n")
    print(prompt)


    # ------------------------
    # Generate Answer (optional)
    # ------------------------

    if not generate:
        # Streaming callers generate once via generate_response_stream(prompt).
        return {
            "answer": "",
            "sources": sources,
            "prompt": prompt,
        }

    answer = resolve_answer(generate_response(prompt), sources)
    answer, sources = finalize_answer_citations(answer, sources)

    return {
        "answer": answer,
        "sources": sources,
        "prompt": prompt
    }



# ========================
# Terminal Test
# ========================

if __name__ == "__main__":

    question = input(
        "Ask a question: "
    )

    response = ask_question(
        question
    )

    print("\n========== ANSWER ==========\n")
    print(response["answer"])


    print("\nSources:")

    for source in response["sources"]:

        print(
            f"- {source['filename']} | "
            f"Page {source['page']} | "
            f"Chunk {source['chunk_id']} | "
            f"Relevance {source['relevance']}%"
        )
