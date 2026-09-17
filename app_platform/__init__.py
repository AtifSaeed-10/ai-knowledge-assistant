"""
Platform layer: request identity, quotas, and ownership guards.

Sits above the RAG core. Nothing in here imports rag.py; the API shell
resolves an actor, enforces limits, and filters document ids before the
retrieval pipeline is called.

Named app_platform (not platform) because a top-level `platform` package
shadows the standard library module that chromadb and attrs import.
"""
