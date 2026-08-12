import os
import gc

from pypdf import PdfReader
from fastembed import TextEmbedding
import chromadb
from database.document_store import (
    update_document_status,
    update_document_metadata
)
from config import (
    CHROMA_DB_PATH,
    COLLECTION_NAME,
)
from chunking import (
    build_chunks_from_pages,
    chroma_metadata_for_chunk,
)
from bm25_index import bm25_index


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

    update_document_status(
        document_id,
        "extracting"
    )

    # ------------------------
    # Load PDF
    # ------------------------
    reader = PdfReader(pdf_path)

    pages = []

    for page_number, page in enumerate(reader.pages, start=1):

        page_text = page.extract_text()

        if page_text and page_text.strip():
            pages.append(
                {
                    "page_number": page_number,
                    "text": page_text
                }
            )

    update_document_status(
        document_id,
        "chunking"
    )

    # ------------------------
    # Chunking (RAG V2 Phase 1)
    # Document-level, structure-aware; page spans kept as metadata.
    # ------------------------
    chunks = build_chunks_from_pages(pages, document_id)

    print(f"Chunks created: {len(chunks)}")

    update_document_metadata(
        document_id,
        len(pages),
        len(chunks)
    )

    if not chunks:
        print("⚠️ No text extracted from PDF.")
        return

    # ------------------------
    # Register document
    # ------------------------

    print(
        f"Using document ID: {document_id}"
    )

    print(
        f"Document registered: {document_id}"
    )

    # ------------------------
    # Chroma DB setup
    # ------------------------
    client = chromadb.PersistentClient(
        path=CHROMA_DB_PATH
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    update_document_status(
        document_id,
        "embedding"
    )

    # ------------------------
    # Embeddings + Store in batches
    # ------------------------

    batch_size = 50
    filename = os.path.basename(pdf_path)

    for start in range(0, len(chunks), batch_size):

        end = start + batch_size

        batch_chunks = [
            chunk["text"]
            for chunk in chunks[start:end]
        ]

        print(
            f"Embedding chunks {start} to {end}"
        )

        batch_embeddings = list(
            model.embed(batch_chunks)
        )
        update_document_status(
            document_id,
            "indexing"
        )
        collection.add(
            ids=[
                f"{document_id}_{i}"
                for i in range(
                    start,
                    min(end, len(chunks))
                )
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
            ]
        )

        # Free memory after each batch
        del batch_embeddings
        gc.collect()

    update_document_status(
        document_id,
        "ready"
    )

    # Chroma corpus changed — rebuild BM25 on next retrieval.
    bm25_index.invalidate()

    print("✅ PDF indexed successfully!")

    return document_id
