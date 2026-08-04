import chromadb
from fastembed import TextEmbedding

from llm_service import generate_response
from retrieval_logger import log_retrieval
from query_rewriter import rewrite_query
from config import (
    CHROMA_DB_PATH,
    COLLECTION_NAME,
    TOP_K,
    SIMILARITY_THRESHOLD,
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
# Retrieval
# ========================
def retrieve_chunks(
    question,
    document_ids=None
):

    collection = get_collection()

    question_embedding = list(
        model.embed([question])
    )[0]

    if document_ids:

        if len(document_ids) == 1:

            results = collection.query(
                query_embeddings=[question_embedding],
                n_results=TOP_K,
                where={
                    "document_id": document_ids[0]
                }
            )

        else:

            results = collection.query(
                query_embeddings=[question_embedding],
                n_results=TOP_K,
                where={
                    "$or": [
                        {"document_id": id}
                        for id in document_ids
                    ]
                }
            )

    else:

        results = collection.query(
            query_embeddings=[question_embedding],
            n_results=TOP_K
        )


    print("\n========== RETRIEVAL DEBUG ==========")
    print("Question:", question)
    print("Document IDs:", document_ids)

    print(
        "Chunks found:",
        len(results["documents"][0])
    )

    print(
        "Distances:",
        results["distances"][0]
    )

    print(
        "Metadata:"
    )

    for meta in results["metadatas"][0]:
        print(meta)


    return {
        "chunks": results["documents"][0],
        "distances": results["distances"][0],
        "metadata": results["metadatas"][0],
        "ids": results["ids"][0]
    }


# ========================
# RAG Pipeline
# ========================

def ask_question(
    question: str,
    history=None,
    document_ids=None
):


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


    retrieval_result = retrieve_chunks(
        search_query,
        document_ids
        )


    chunks = retrieval_result["chunks"]
    distances = retrieval_result["distances"]
    metadata = retrieval_result["metadata"]
    ids = retrieval_result["ids"]


    # ------------------------
    # Log Retrieval
    # ------------------------
    #

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
            "sources": []
        }



    # ------------------------
    # Similarity Filtering
    # ------------------------

    filtered_chunks = []
    filtered_distances = []
    filtered_metadata = []
    filtered_ids = []


    for chunk, distance, meta, chunk_id in zip(
        chunks,
        distances,
        metadata,
        ids
    ):

        if distance <= SIMILARITY_THRESHOLD:

            filtered_chunks.append(chunk)
            filtered_distances.append(distance)
            filtered_metadata.append(meta)
            filtered_ids.append(chunk_id)



    if not filtered_chunks:

        return {
            "answer": "I don't have enough information in the provided context.",
            "sources": []
        }



    # Replace original retrieval with filtered retrieval

    chunks = filtered_chunks
    distances = filtered_distances
    metadata = filtered_metadata
    ids = filtered_ids



    # ------------------------
    # Debug Output
    # ------------------------

    print("\n========== RETRIEVED CHUNKS ==========\n")


    for i, (chunk, distance) in enumerate(
        zip(chunks, distances),
        start=1
    ):

        print(f"Chunk {i}")
        print(f"Distance: {distance:.4f}")
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
    # Generate Answer
    # ------------------------

    answer = generate_response(prompt)


    # ------------------------
    # Build Citations
    # ------------------------

    sources = []


    for chunk_id, distance, meta in zip(
        ids,
        distances,
        metadata
    ):

        relevance = round(
            (1 - distance) * 100
        )

        relevance = max(
            0,
            min(
                100,
                relevance
            )
        )


        sources.append(
            {
                "document_id": meta["document_id"],
                "filename": meta["filename"],
                "page": meta["page_number"],
                "chunk_id": chunk_id,
                "relevance": relevance
            }
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