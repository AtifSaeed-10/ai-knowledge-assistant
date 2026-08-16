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

DATA_DIR = os.getenv(
    "DATA_DIR",
    "./data"
)

# Agentic Mode is foundation-only until a later phase. Keep disabled.
AGENTIC_MODE_ENABLED = os.getenv(
    "AGENTIC_MODE_ENABLED",
    "false"
).strip().lower() in {"1", "true", "yes", "on"}

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
# A/B rerankers (FastEmbed TextCrossEncoder / ONNX). Default: BGE.
# Switch via RERANKER_MODEL env: full HF id or alias "bge" / "minilm".
RERANKER_MODEL_BGE = "BAAI/bge-reranker-base"
RERANKER_MODEL_MINILM = "Xenova/ms-marco-MiniLM-L-6-v2"

RERANKER_MODEL_ALIASES: dict[str, str] = {
    "bge": RERANKER_MODEL_BGE,
    "minilm": RERANKER_MODEL_MINILM,
    "ms-marco-minilm": RERANKER_MODEL_MINILM,
}


def resolve_reranker_model(value: str) -> str:
    """Map short aliases to HuggingFace model ids; pass through full ids."""
    trimmed = value.strip()
    alias = RERANKER_MODEL_ALIASES.get(trimmed.lower())
    return alias if alias is not None else trimmed


RERANKER_MODEL = resolve_reranker_model(
    os.getenv("RERANKER_MODEL", RERANKER_MODEL_BGE)
)

# Fused hybrid pool size passed into the reranker (after RRF; before BGE).
RERANK_CANDIDATE_K = int(
    os.getenv("RERANK_CANDIDATE_K", 20)
)

# Final evidence count after reranking (defaults to TOP_K).
RERANK_TOP_K = int(
    os.getenv("RERANK_TOP_K", str(TOP_K))
)

# Max characters of each chunk sent to BGE (full text kept for LLM context).
# Conservative for ~512-token cross-encoder with query + passage.
RERANK_MAX_CHARS = int(
    os.getenv("RERANK_MAX_CHARS", 800)
)

# Optional minimum raw reranker logit. Empty/unset disables the floor.
_raw_rerank_min = os.getenv("RERANK_MIN_SCORE", "").strip()
RERANK_MIN_SCORE = (
    float(_raw_rerank_min) if _raw_rerank_min else None
)

# Minimum sigmoid relevance [0, 100] for final evidence slots (LLM context).
EVIDENCE_MIN_RELEVANCE = int(
    os.getenv("EVIDENCE_MIN_RELEVANCE", "25")
)

# Minimum relevance shown in citations (can be stricter than evidence floor).
CITATION_MIN_RELEVANCE = int(
    os.getenv("CITATION_MIN_RELEVANCE", "30")
)

# Near-duplicate overlap ratio for final evidence [0.0, 1.0].
EVIDENCE_NEAR_DUP_RATIO = float(
    os.getenv("EVIDENCE_NEAR_DUP_RATIO", "0.72")
)

# Raw MiniLM floor for dual-source fallback when relevance filter is empty.
EVIDENCE_FALLBACK_MIN_RERANK = float(
    os.getenv("EVIDENCE_FALLBACK_MIN_RERANK", "-5.0")
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
