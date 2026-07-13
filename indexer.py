import gc
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from fastembed import TextEmbedding
import chromadb

from config import (
    CHROMA_DB_PATH,
    COLLECTION_NAME,
)

# ========================
# Embedding Model (loaded once)
# ========================
model =TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

# ========================
# PDF Indexing Pipeline
# ========================
def index_pdf(pdf_path: str):

    # ------------------------
    # Load PDF
    # ------------------------
    reader = PdfReader(pdf_path)

    pages_text = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            pages_text.append(page_text)

    text = "\n".join(pages_text)

    # ------------------------
    # Chunking
    # ------------------------
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    chunks = splitter.split_text(text)

    print(f"Chunks created: {len(chunks)}")

    if not chunks:
        print("⚠️ No text extracted from PDF.")
        return

    # ------------------------
    # Chroma DB setup
    # ------------------------
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    # Clean old collection safely
    if COLLECTION_NAME in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION_NAME)

    collection = client.get_or_create_collection(name=COLLECTION_NAME)

# ------------------------
# Embeddings + Store in batches
# ------------------------

batch_size = 50

for start in range(0, len(chunks), batch_size):

    end = start + batch_size

    batch_chunks = chunks[start:end]

    print(f"Embedding chunks {start} to {end}")

    batch_embeddings = list(model.embed(batch_chunks))

    collection.add(
        ids=[
            str(i)
            for i in range(start, min(end, len(chunks)))
        ],
        documents=batch_chunks,
        embeddings=batch_embeddings,
        metadatas=[
            {"chunk_index": i}
            for i in range(start, min(end, len(chunks)))
        ]
    )
    del batch_embeddings
    gc.collect()

print("✅ PDF indexed successfully!")