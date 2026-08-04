import chromadb

from config import (
    CHROMA_DB_PATH,
    COLLECTION_NAME
)

from database.document_store import (
    get_all_documents,
    get_document,
    delete_document
)

client = chromadb.PersistentClient(
    path=CHROMA_DB_PATH
)

def list_documents():

    return get_all_documents()

def remove_document(document_id):

    collection = client.get_collection(
        name=COLLECTION_NAME
    )


    collection.delete(
        where={
            "document_id": document_id
        }
    )


    deleted = delete_document(
        document_id
    )


    return deleted

def get_document_details(document_id):

    return get_document(
        document_id
    )