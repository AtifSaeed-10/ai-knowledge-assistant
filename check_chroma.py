import chromadb

client = chromadb.PersistentClient(
    path="./chroma_db"
)

collection = client.get_collection(
    "ml_notes"
)

data = collection.get(
    include=["metadatas"]
)

ids = set()

for meta in data["metadatas"]:
    ids.add(meta["document_id"])

print("DOCUMENT IDS IN CHROMA:")

for i in ids:
    print(i)