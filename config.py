import os
from dotenv import load_dotenv

load_dotenv()


LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "qwen2.5:3b"
)

OLLAMA_HOST = os.getenv(
    "OLLAMA_HOST",
    "http://localhost:11434"
)

CHROMA_DB_PATH = os.getenv(
    "CHROMA_DB_PATH",
    "./chroma_db"
)

COLLECTION_NAME = os.getenv(
    "COLLECTION_NAME",
    "ml_notes"
)
SQLITE_DB_PATH = os.getenv(
    "SQLITE_DB_PATH",
    "./data/documents.db"
)

TOP_K = int(
    os.getenv("TOP_K", 5)
)

# Hybrid retrieval: per-retriever candidate pool size before fusion.
CANDIDATE_K = int(
    os.getenv("CANDIDATE_K", 20)
)

# Reciprocal Rank Fusion constant (standard default is 60).
RRF_K = int(
    os.getenv("RRF_K", 60)
)

# ========================
# Phase 3 — Cross-encoder reranking
# ========================

RERANKER_MODEL = os.getenv(
    "RERANKER_MODEL",
    "BAAI/bge-reranker-base"
)

# Fused hybrid pool size passed into the reranker (deduped).
RERANK_CANDIDATE_K = int(
    os.getenv("RERANK_CANDIDATE_K", 40)
)

# Final evidence count after reranking (defaults to TOP_K).
RERANK_TOP_K = int(
    os.getenv("RERANK_TOP_K", str(TOP_K))
)

# Optional minimum raw reranker logit. Empty/unset disables the floor.
_raw_rerank_min = os.getenv("RERANK_MIN_SCORE", "").strip()
RERANK_MIN_SCORE = (
    float(_raw_rerank_min) if _raw_rerank_min else None
)

# Legacy dense-distance gate (Phase 1/2). Not applied to reranker scores.
SIMILARITY_THRESHOLD = float(
    os.getenv("SIMILARITY_THRESHOLD", 0.7)
)
# ========================
# Memory Configuration
# ========================

MEMORY_WINDOW = int(
    os.getenv("MEMORY_WINDOW", 6)
)
# ========================
# LLM Configuration
# ========================

PRIMARY_LLM = os.getenv(
    "PRIMARY_LLM",
    "ollama"
)

FALLBACK_LLM = os.getenv(
    "FALLBACK_LLM",
    "groq"
)
#................
GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)
