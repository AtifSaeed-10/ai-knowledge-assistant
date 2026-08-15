import chromadb
from fastembed import TextEmbedding

from llm_service import generate_response
from retrieval_logger import log_retrieval
from query_rewriter import rewrite_query
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
from hybrid_retrieval import (
    retrieve_dense,
    retrieve_bm25,
    fuse_results,
    retrieve_candidates as hybrid_retrieve_candidates,
)


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


# ========================
# RAG Pipeline
# ========================

def ask_question(
    question: str,
    history=None,
    document_ids=None,
    *,
    generate: bool = True,
):
    """
    Run retrieval/rerank, build prompt + citations, optionally generate.

    generate=True  → non-streaming /chat (default; full answer)
    generate=False → /chat/stream prepares prompt once; caller streams LLM
    """


    # ------------------------
    # Query Rewriting
    # ------------------------

    if history:
        search_query = rewrite_query(
            question,
            history
        )
    else:
        search_query = question


    print("\n========== SEARCH QUERY ==========")
    print(search_query)


    retrieval_result = retrieve_candidates(
        search_query,
        document_ids
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
    # Build Context
    # ------------------------

    context = "\n\n".join(chunks)

    # ------------------------
    # Format Conversation History
    # ------------------------

    if history:

        conversation = "\n".join(
            [
                f"{msg['role'].capitalize()}: {msg['content']}"
                for msg in history
            ]
        )

    else:
        conversation = "No previous conversation."


    # ------------------------
    # Prompt
    # ------------------------

    prompt = f"""

You are a precise question-answering system.

Rules:
- Use ONLY the provided context.
- If the answer is not in the context, say:
  "I don't have enough information in the provided context."
- Do NOT use external knowledge.
- Do NOT guess or hallucinate.


Conversation History:

{conversation}


Document Context:

{context}


Current Question:

{question}


Answer:

""".strip()


    print("\n========== PROMPT SENT TO LLM ==========\n")
    print(prompt)


    # ------------------------
    # Build Citations
    # ------------------------

    sources = []


    for idx, (chunk_id, meta) in enumerate(zip(ids, metadata)):

        if idx < len(relevances) and relevances[idx] is not None:
            relevance = int(relevances[idx])
        else:
            # Fallback citation relevance if lists are misaligned.
            relevance = 0

        relevance = max(0, min(100, relevance))

        if relevance < CITATION_MIN_RELEVANCE:
            continue


        sources.append(
            {
                "document_id": meta["document_id"],
                "filename": meta["filename"],
                "page": meta["page_number"],
                "chunk_id": chunk_id,
                "relevance": relevance
            }
        )


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

    answer = generate_response(prompt)

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
