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
