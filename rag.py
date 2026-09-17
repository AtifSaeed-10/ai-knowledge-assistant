import chromadb
from fastembed import TextEmbedding

from llm_service import generate_response
from retrieval_logger import log_retrieval
from query_rewriter import rewrite_query
from conversation_query import analyze_turn, infer_subject_phrase
from answer_prompt import build_answer_prompt
from answer_planner import format_plan_for_prompt, plan_answer
from wide_recall import lexical_probe_queries, recall_settings
from evidence_focus import citation_allowlist, format_evidence_notes
from modes import normalize_mode, insufficient_context_payload
from config import (
    CHROMA_DB_PATH,
    COLLECTION_NAME,
    TOP_K,
    CANDIDATE_K,
    RERANK_CANDIDATE_K,
    RECALL_TOP_K,
    RRF_K,
    CITATION_MIN_RELEVANCE,
)
from bm25_index import bm25_index
from reranker import reranker
from citation_resolver import evidence_id_for_index, resolve_answer
from claim_validator import finalize_answer_citations
from evidence_mapping import make_snippet
from evidence_state import evidence_state_for_chunk, visible_sources
from grounding_verifier import verify_and_repair_refusal
from index_hygiene import resolve_retrieval_scope
from query_normalize import (
    build_vocabulary,
    correct_query,
    detect_small_talk,
    needs_correction,
    small_talk_answer,
)
from hybrid_retrieval import (
    retrieve_dense,
    retrieve_bm25,
    fuse_results,
    retrieve_candidates as hybrid_retrieve_candidates,
)


def _display_filename(document_id: str, indexed_name: str) -> str:
    """
    Chunk metadata stores the PDF's on-disk name, which is `{document_id}.pdf`.
    Citations should carry the name the reader uploaded, so look it up in the
    documents table and fall back to the indexed value.
    """
    document_id = str(document_id or "")
    if not document_id:
        return indexed_name

    cached = _FILENAME_CACHE.get(document_id)
    if cached is not None:
        return cached or indexed_name

    try:
        from database.document_store import get_document

        record = get_document(document_id) or {}
        original = str(record.get("filename") or "").strip()
    except Exception:
        original = ""

    _FILENAME_CACHE[document_id] = original
    return original or indexed_name


_FILENAME_CACHE: dict[str, str] = {}

_VOCABULARY_CACHE: dict[str, dict[str, int]] = {}


def _indexed_vocabulary(document_ids: list[str] | None) -> dict[str, int]:
    """
    Words that appear in the scoped passages, cached until the corpus changes.
    A typo can only ever be corrected into one of these.

    The BM25 index is loaded here so spelling does not run against an empty
    dictionary — that used to leave "entrpy" uncorrected.
    """
    bm25_index.ensure_loaded(get_collection())
    scope_key = ",".join(sorted(document_ids or [])) or "*"
    key = f"{bm25_index.fingerprint or ''}|{scope_key}"

    cached = _VOCABULARY_CACHE.get(key)
    if cached is not None:
        return cached

    vocabulary = build_vocabulary(bm25_index.corpus_texts(document_ids))
    _VOCABULARY_CACHE.clear()
    _VOCABULARY_CACHE[key] = vocabulary
    return vocabulary


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
    citation_eligible: list | None = None,
) -> tuple[list[dict], list[str | None]]:
    """
    Assign stable E1..En ids to every unique recall-pool chunk.

    Citeability is a separate evidence_state. The relevance floor and
    allowlist decide citeable vs page_only; they do not drop the E#.
    """
    allowed_citations = citation_allowlist(chunks, search_query, analysis)
    flags = list(citation_eligible or [])
    sources: list[dict] = []
    evidence_ids: list[str | None] = [None] * len(chunks)
    seen_chunk_ids: set[str] = set()

    for idx, (chunk_id, meta) in enumerate(zip(ids, metadata)):
        if idx < len(relevances) and relevances[idx] is not None:
            relevance = int(relevances[idx])
        else:
            relevance = 0
        relevance = max(0, min(100, relevance))
        eligible = (
            bool(flags[idx])
            if idx < len(flags)
            else relevance >= CITATION_MIN_RELEVANCE
        )
        allowlisted = allowed_citations is None or idx in allowed_citations
        if chunk_id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(chunk_id)

        meta = meta or {}
        page = _citation_page(meta)
        evidence_id = evidence_id_for_index(len(sources) + 1)
        evidence_ids[idx] = evidence_id
        chunk_text = chunks[idx] if idx < len(chunks) else ""
        state = evidence_state_for_chunk(
            relevance=relevance,
            citation_eligible=eligible,
            allowlisted=allowlisted,
        )
        sources.append(
            {
                "document_id": meta.get("document_id") or "",
                "filename": _display_filename(
                    meta.get("document_id") or "",
                    meta.get("filename") or "",
                ),
                "page": page,
                "chunk_id": chunk_id,
                "relevance": relevance,
                "evidence_id": evidence_id,
                "citation_eligible": state == "citeable",
                "evidence_state": state,
                "snippet": make_snippet(
                    chunk_text if isinstance(chunk_text, str) else ""
                ),
                "quote": None,
            }
        )

    return _dedupe_sources(sources), evidence_ids


def _build_recall_candidates(
    chunks: list,
    ids: list,
    metadata: list,
    relevances: list,
    evidence_ids: list,
    citation_eligible: list | None = None,
) -> list[dict]:
    """
    Full retrieval pool for claim orchestration, including non-citeable chunks.

    Full chunk text stays server-side; it is not sent as a client citation.
    """
    flags = list(citation_eligible or [])
    candidates: list[dict] = []
    for idx, chunk_id in enumerate(ids or []):
        meta = metadata[idx] if idx < len(metadata) and metadata[idx] else {}
        if idx < len(relevances) and relevances[idx] is not None:
            relevance = int(relevances[idx])
        else:
            relevance = 0
        relevance = max(0, min(100, relevance))
        eligible = bool(flags[idx]) if idx < len(flags) else relevance >= CITATION_MIN_RELEVANCE
        evidence_id = evidence_ids[idx] if idx < len(evidence_ids) else None
        chunk_text = chunks[idx] if idx < len(chunks) else ""
        candidates.append(
            {
                "document_id": meta.get("document_id") or "",
                "filename": meta.get("filename") or "",
                "page": _citation_page(meta),
                "chunk_id": chunk_id,
                "relevance": relevance,
                "evidence_id": evidence_id,
                "citation_eligible": eligible,
                "text": chunk_text if isinstance(chunk_text, str) else "",
                "snippet": make_snippet(
                    chunk_text if isinstance(chunk_text, str) else ""
                ),
            }
        )
    return candidates


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
# Dense + BM25 → RRF pool → BGE reranker → recall pool (citations are a subset).


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
        top_k=top_k if top_k is not None else RECALL_TOP_K,
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
    n_primary = len(primary.get("ids") or [])
    list_fields = (
        "chunks",
        "distances",
        "metadata",
        "ids",
        "dense_distances",
        "bm25_scores",
        "rrf_scores",
        "reranker_scores",
        "relevances",
        "citation_eligible",
        "recall_fallbacks",
    )
    merged = {key: list(primary.get(key) or []) for key in list_fields}
    for bool_field in ("citation_eligible", "recall_fallbacks"):
        while len(merged[bool_field]) < n_primary:
            merged[bool_field].append(False)
    added = 0
    for idx, chunk_id in enumerate(supplemental.get("ids") or []):
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        merged["chunks"].append(supplemental["chunks"][idx])
        for field in list_fields[1:]:
            values = supplemental.get(field) or []
            if idx < len(values):
                merged[field].append(values[idx])
            elif field == "citation_eligible":
                rels = supplemental.get("relevances") or []
                relevance = int(rels[idx] or 0) if idx < len(rels) else 0
                merged[field].append(relevance >= CITATION_MIN_RELEVANCE)
            elif field == "recall_fallbacks":
                merged[field].append(bool(supplemental.get("recall_fallback")))
            else:
                merged[field].append(None)
        added += 1
        if added >= max_extra:
            break

    if added == 0:
        return primary

    out = dict(primary)
    for field, values in merged.items():
        out[field] = values
    out["recall_fallback"] = bool(out.get("recall_fallback")) or any(
        merged.get("recall_fallbacks") or []
    )
    return out


def _chunks_from_ids(chunk_ids: list[str]) -> dict:
    """Load stored chunks by id so neighboring pages can join the recall pool."""
    empty = {"ids": [], "chunks": [], "metadata": []}
    wanted = [item for item in chunk_ids if item]
    if not wanted:
        return empty
    try:
        payload = get_collection().get(ids=wanted, include=["documents", "metadatas"])
    except Exception:
        return empty
    got_ids = payload.get("ids") or []
    documents = payload.get("documents") or []
    metadatas = payload.get("metadatas") or []
    ids: list[str] = []
    chunks: list[str] = []
    metadata: list[dict] = []
    for index, chunk_id in enumerate(got_ids):
        if not chunk_id:
            continue
        text = documents[index] if index < len(documents) else ""
        if not isinstance(text, str) or not text.strip():
            continue
        meta = metadatas[index] if index < len(metadatas) else {}
        ids.append(chunk_id)
        chunks.append(text)
        metadata.append(meta if isinstance(meta, dict) else {})
    return {"ids": ids, "chunks": chunks, "metadata": metadata}


def _retrieval_from_hits(hits: list[dict], limit: int) -> dict:
    """Shape BM25/dense hits like retrieve_candidates so they can merge."""
    ids: list[str] = []
    chunks: list[str] = []
    metadata: list[dict] = []
    for hit in hits[: max(0, limit)]:
        chunk_id = str(hit.get("id") or "")
        text = hit.get("text") or ""
        if not chunk_id or not isinstance(text, str) or not text.strip():
            continue
        ids.append(chunk_id)
        chunks.append(text)
        meta = hit.get("metadata") or {}
        metadata.append(meta if isinstance(meta, dict) else {})
    n = len(ids)
    return {
        "ids": ids,
        "chunks": chunks,
        "metadata": metadata,
        "distances": [None] * n,
        "relevances": [0] * n,
        "citation_eligible": [True] * n,
        "recall_fallbacks": [False] * n,
    }


def _attach_neighbor_chunks(result: dict, limit: int) -> dict:
    if limit <= 0 or not result.get("ids"):
        return result
    have = set(result.get("ids") or [])
    wanted: list[str] = []
    # Later/supplemental chunks first so a rare event still gets its page neighbors.
    for meta in reversed(list(result.get("metadata") or [])):
        meta = meta or {}
        for key in ("next_chunk_id", "prev_chunk_id"):
            neighbor = str(meta.get(key) or "").strip()
            if neighbor and neighbor not in have and neighbor not in wanted:
                wanted.append(neighbor)
            if len(wanted) >= limit:
                break
        if len(wanted) >= limit:
            break
    fetched = _chunks_from_ids(wanted)
    if not fetched["ids"]:
        return result
    n = len(fetched["ids"])
    supplemental = {
        "ids": fetched["ids"],
        "chunks": fetched["chunks"],
        "metadata": fetched["metadata"],
        "distances": [None] * n,
        "relevances": [0] * n,
        "citation_eligible": [True] * n,
        "recall_fallbacks": [False] * n,
    }
    return _merge_retrieval_results(result, supplemental, max_extra=limit)


def _retrieve_with_plan(
    search_query: str,
    plan,
    document_ids=None,
) -> dict:
    """Primary hybrid retrieval, plus cheap lexical probes and page neighbors."""
    wide = bool(getattr(plan, "wide_recall", False) or getattr(plan, "multi_topic", False))
    settings = recall_settings(wide=wide)
    primary = retrieve_candidates(
        search_query,
        document_ids,
        candidate_k=settings["candidate_k"],
        rerank_candidate_k=settings["rerank_candidate_k"],
        top_k=settings["top_k"],
    )
    sub_queries = [
        item.strip()
        for item in (getattr(plan, "sub_queries", None) or [])
        if item and item.strip()
    ]
    probe_keys = {
        item.strip().lower() for item in lexical_probe_queries(search_query)
    }
    result = primary
    extras_budget = settings["extras_budget"]
    per_query_k = settings["per_query_k"]
    normalized_primary = search_query.strip().lower()
    hybrid_left = 2
    for sub_query in sub_queries[:6]:
        if extras_budget <= 0 or hybrid_left <= 0:
            break
        key = sub_query.strip().lower()
        if key == normalized_primary or key in probe_keys:
            continue
        supplemental = retrieve_candidates(
            sub_query,
            document_ids,
            top_k=per_query_k,
            candidate_k=settings["candidate_k"],
            rerank_candidate_k=settings["rerank_candidate_k"],
        )
        hybrid_left -= 1
        before = len(result.get("ids") or [])
        result = _merge_retrieval_results(
            result,
            supplemental,
            max_extra=extras_budget,
        )
        extras_budget -= max(0, len(result.get("ids") or []) - before)

    if extras_budget > 0:
        for probe in lexical_probe_queries(search_query):
            if extras_budget <= 0:
                break
            try:
                hits = retrieve_bm25(
                    probe,
                    collection=get_collection(),
                    document_ids=document_ids,
                    k=per_query_k,
                )
            except Exception:
                continue
            before = len(result.get("ids") or [])
            result = _merge_retrieval_results(
                result,
                _retrieval_from_hits(hits, per_query_k),
                max_extra=extras_budget,
            )
            extras_budget -= max(0, len(result.get("ids") or []) - before)

    return _attach_neighbor_chunks(result, settings["neighbors"])


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

    # "hi" and "thanks" have no answer in any PDF; retrieving for them would
    # only return whatever chunk happens to score least badly.
    small_talk = detect_small_talk(question)
    if small_talk:
        return {
            "answer": small_talk_answer(small_talk),
            "sources": [],
            "prompt": None,
        }

    product_mode = normalize_mode(mode)
    scoped_ids, abort_search = resolve_retrieval_scope(product_mode, document_ids)
    if abort_search:
        return insufficient_context_payload()
    document_ids = scoped_ids

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

    # Typed "sprved lernng"? Search for the words the documents actually use.
    # This changes the query only — whether an answer exists is still decided
    # by the passages.
    spelling_note = None
    if needs_correction(search_query):
        corrected = correct_query(search_query, _indexed_vocabulary(document_ids))
        if corrected.strip() and corrected != search_query:
            spelling_note = corrected.strip()
            search_query = spelling_note

    print("\n========== SEARCH QUERY ==========")
    print(search_query)
    if spelling_note:
        print(f"(spelling corrected from: {question})")
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
    print(
        "Pre-LLM rank: "
        f"page={retrieval_result.get('rank1_page')} "
        f"id={retrieval_result.get('rank1_id')} "
        f"gap12={retrieval_result.get('score_gap_12')} "
        f"gating={retrieval_result.get('gating_path')} "
        f"zero_result={retrieval_result.get('zero_result')}"
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
        retrieval_result.get("citation_eligible"),
    )
    recall_candidates = _build_recall_candidates(
        chunks,
        ids,
        metadata,
        relevances,
        evidence_ids,
        retrieval_result.get("citation_eligible"),
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
        spelling_note=spelling_note,
        wide_recall=bool(getattr(answer_plan_obj, "wide_recall", False)),
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
            "recall_candidates": recall_candidates,
            "analysis": analysis,
        }

    answer = resolve_answer(generate_response(prompt), sources)
    answer, _grounding = verify_and_repair_refusal(
        answer,
        question=question,
        prompt=prompt,
        sources=sources,
        recall_candidates=recall_candidates,
        analysis=analysis,
        generate_fn=generate_response,
    )
    answer, sources = finalize_answer_citations(
        answer,
        sources,
        recall_candidates=recall_candidates,
    )
    sources = visible_sources(
        sources,
        answer,
        recall_candidates=recall_candidates,
    )

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
