import chromadb
from fastembed import TextEmbedding
from llm_service import generate_response

from config import (
    CHROMA_DB_PATH,
    COLLECTION_NAME,
    TOP_K,
    SIMILARITY_THRESHOLD,
)

# ========================
# Load once (important)
# ========================
client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def ask_question(question: str):

    # ------------------------
    # Get collection
    # ------------------------
    collection = client.get_collection(COLLECTION_NAME)

    # ------------------------
    # Embed query (FIXED)
    # ------------------------
    question_embedding = list(model.embed([question]))[0]

    # ------------------------
    # Vector search
    # ------------------------
    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=TOP_K
    )

    retrieved_chunks = results["documents"][0]
    retrieval_distances = results["distances"][0]

    if not retrieved_chunks:
        return "No relevant information found in the document."

    # ------------------------
    # Retrieval Gate
    # ------------------------
    best_distance = retrieval_distances[0]

    if best_distance > SIMILARITY_THRESHOLD:
        return "No relevant information found in the document."

    # ------------------------
    # Debug output (Milestone 2 ready)
    # ------------------------
    print("\n========== RETRIEVED CHUNKS ==========\n")

    for i, (chunk, distance) in enumerate(zip(retrieved_chunks, retrieval_distances), start=1):
        print(f"Chunk {i}")
        print(f"Distance: {distance:.4f}")
        print("-" * 50)
        print(chunk)
        print()

    # ------------------------
    # Context building
    # ------------------------
    context = "\n\n".join(retrieved_chunks)

    # ------------------------
    # Prompt (strict RAG guardrails)
    # ------------------------
    prompt = f"""
You are a precise question-answering system.

Rules:
- Use ONLY the provided context.
- If the answer is not in the context, say:
  "I don't have enough information in the provided context."
- Do NOT use external knowledge.
- Do NOT guess or hallucinate.

Context:
{context}

Question:
{question}

Answer:
""".strip()

    print("\n========== PROMPT SENT TO LLM ==========\n")
    print(prompt)

    # ------------------------
    # LLM call
    # ------------------------
    return generate_response(prompt)


if __name__ == "__main__":

    question = input("Ask a question: ")

    answer = ask_question(question)

    print("\n========== ANSWER ==========\n")
    print(answer)