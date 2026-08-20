import gc
import logging
import os

from fastembed import TextEmbedding
import chromadb

from bm25_index import bm25_index
from chunking import (
    build_chunks_from_pages,
    chroma_metadata_for_chunk,
)
from config import (
    CHROMA_DB_PATH,
    COLLECTION_NAME,
)
from database.document_store import (
    mark_document_index_failed,
    update_document_metadata,
    update_document_index_error,
    update_document_status,
)
from database.evidence_store import replace_document_evidence
from evidence_mapping import build_document_evidence
from pdf_extraction import (
    INDEX_FAILURE_NO_TEXT,
    extract_pages_from_pdf,
)

logger = logging.getLogger(__name__)

# ========================
# Embedding Model (loaded once)
# ========================
model = TextEmbedding(
    model_name="BAAI/bge-small-en-v1.5"
)


# ========================
# PDF Indexing Pipeline
# ========================
def index_pdf(pdf_path: str, document_id: str):
    update_document_status(document_id, "extracting")
    update_document_index_error(document_id, None)

    try:
        extraction = extract_pages_from_pdf(
            pdf_path,
            document_id=document_id,
        )
        pages = extraction.pages

        update_document_status(document_id, "chunking")

        chunks = build_chunks_from_pages(pages, document_id)

        logger.info(
            "index_pdf document_id=%s chunks_created=%s engine=%s",
            document_id,
            len(chunks),
            extraction.engine_used,
        )

        update_document_metadata(
            document_id,
            extraction.total_pages,
            len(chunks),
        )

        if not chunks:
            mark_document_index_failed(document_id, INDEX_FAILURE_NO_TEXT)
            logger.warning(
                "index_pdf document_id=%s failed: no chunks (engine=%s pages_with_text=%s)",
                document_id,
                extraction.engine_used,
                extraction.pages_with_text,
            )
            return

        try:
            evidence = build_document_evidence(
                pdf_path,
                document_id,
                pages,
                chunks,
                text_engine=extraction.engine_used,
            )
            replace_document_evidence(document_id, evidence)
        except Exception:
            logger.exception(
                "index_pdf document_id=%s evidence mapping failed; continuing index",
                document_id,
            )

        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        collection = client.get_or_create_collection(name=COLLECTION_NAME)

        update_document_status(document_id, "embedding")

        batch_size = 50
        filename = os.path.basename(pdf_path)

        for start in range(0, len(chunks), batch_size):
            end = start + batch_size

            batch_chunks = [chunk["text"] for chunk in chunks[start:end]]

            logger.info(
                "index_pdf document_id=%s embedding chunks %s to %s",
                document_id,
                start,
                end,
            )

            batch_embeddings = list(model.embed(batch_chunks))
            update_document_status(document_id, "indexing")
            collection.add(
                ids=[
                    f"{document_id}_{i}"
                    for i in range(start, min(end, len(chunks)))
                ],
                documents=batch_chunks,
                embeddings=batch_embeddings,
                metadatas=[
                    chroma_metadata_for_chunk(
                        chunk,
                        document_id,
                        filename,
                    )
                    for chunk in chunks[start:end]
                ],
            )

            del batch_embeddings
            gc.collect()

        update_document_status(document_id, "ready")
        update_document_index_error(document_id, None)
        bm25_index.invalidate()

        logger.info("index_pdf document_id=%s ready chunks=%s", document_id, len(chunks))
        return document_id

    except Exception as exc:
        message = f"Indexing failed: {exc.__class__.__name__}"
        mark_document_index_failed(document_id, message)
        logger.exception(
            "index_pdf document_id=%s failed with exception",
            document_id,
        )
        return
