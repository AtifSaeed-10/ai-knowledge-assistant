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

# Item 4 — query-type retrieval (front-matter / figure / article / listing).
FRONT_MATTER_MAX_PAGE = int(
    os.getenv("FRONT_MATTER_MAX_PAGE", "8")
)
PHRASE_BM25_BOOST = float(
    os.getenv("PHRASE_BM25_BOOST", "2.5")
)
QUERY_TYPE_RESERVED_SLOTS = int(
    os.getenv("QUERY_TYPE_RESERVED_SLOTS", "4")
)
QUERY_TYPE_CANDIDATE_BOOST = int(
    os.getenv("QUERY_TYPE_CANDIDATE_BOOST", "10")
)

# Item 5 — claim-centric orchestration (document-agnostic lexical rebind).
CLAIM_REBIND_MARGIN = float(
    os.getenv("CLAIM_REBIND_MARGIN", "0.12")
)
CLAIM_SUPPORT_MIN = float(
    os.getenv("CLAIM_SUPPORT_MIN", "0.42")
)

# Item 6 — neighbor radius for cross-chunk stitch (always ±1 in code).
REANCHOR_NEIGHBOR_RADIUS = int(
    os.getenv("REANCHOR_NEIGHBOR_RADIUS", "1")
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

# LLM recall-pool size (context slots). Defaults to RERANK_TOP_K.
# Every recall slot gets an E#. Citeable vs page_only uses CITATION_MIN_RELEVANCE.
RECALL_TOP_K = int(
    os.getenv("RECALL_TOP_K", str(RERANK_TOP_K))
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

# Preferred sigmoid relevance [0, 100] for recall slots. Below-floor chunks
# are kept only when the floor would empty a nonempty fused/reranked pool.
EVIDENCE_MIN_RELEVANCE = int(
    os.getenv("EVIDENCE_MIN_RELEVANCE", "25")
)

# Minimum relevance for citeable evidence_state (stricter than the evidence floor).
# Below this, chunks still receive an E# and may surface as page_only.
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

# Held-out MiniLM calibration (audit): entropy true-positive raw ≈ -4.45 must
# clear citation/evidence floors; World Cup true-negative raw ≈ -5.98 must not.
# sigmoid(-4.45 + 4.0) ≈ 39%; sigmoid(-5.98 + 4.0) ≈ 12%.
MINILM_LOGIT_OFFSET = float(
    os.getenv("MINILM_LOGIT_OFFSET", "4.0")
)

# Optional extra shift for BGE (default 0 — BGE logits already sit on sigmoid).
BGE_LOGIT_OFFSET = float(
    os.getenv("BGE_LOGIT_OFFSET", "0.0")
)

# Keep a below-floor neighbor when its raw score is within this logit gap of
# the top chunk. Tight enough that MiniLM entropy vs phone-noise (gap 1.14)
# stays split; wide enough for near-tied WWI pages (gap ≤ 1.0).
RERANK_TIE_MARGIN = float(
    os.getenv("RERANK_TIE_MARGIN", "1.0")
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

def _normalize_provider_name(name: str) -> str:
    raw = (name or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "google": "gemini",
        "google_gemini": "gemini",
        "gemini_api": "gemini",
        "groq_ai": "groq",
        "cerebras_ai": "cerebras",
        "open_router": "openrouter",
        "mistral_ai": "mistral",
        "mistralai": "mistral",
    }
    return aliases.get(raw, raw)


def _csv_providers(value: str | None) -> list[str]:
    if not value:
        return []
    names: list[str] = []
    for part in value.split(","):
        name = _normalize_provider_name(part)
        if name and name not in names:
            names.append(name)
    return names


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


LLM_PRIMARY_PROVIDER = _normalize_provider_name(
    os.getenv("LLM_PRIMARY_PROVIDER")
    or os.getenv("PRIMARY_LLM")
    or "groq"
)

_fallback_raw = os.getenv("LLM_FALLBACK_PROVIDERS")
if _fallback_raw is None:
    legacy = os.getenv("FALLBACK_LLM")
    if legacy:
        LLM_FALLBACK_PROVIDERS = _csv_providers(legacy)
    else:
        LLM_FALLBACK_PROVIDERS = ["gemini", "cerebras", "openrouter", "mistral"]
else:
    LLM_FALLBACK_PROVIDERS = _csv_providers(_fallback_raw)

# Backward-compatible aliases used by older modules.
PRIMARY_LLM = LLM_PRIMARY_PROVIDER
FALLBACK_LLM = LLM_FALLBACK_PROVIDERS[0] if LLM_FALLBACK_PROVIDERS else "gemini"

LLM_REQUEST_TIMEOUT = _env_float("LLM_REQUEST_TIMEOUT", 60.0)
LLM_MAX_RETRIES_PER_PROVIDER = _env_int("LLM_MAX_RETRIES_PER_PROVIDER", 1)

GROQ_API_KEY = os.getenv("GROQ_API_KEY") or ""
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY") or ""
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or ""
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY") or ""
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
