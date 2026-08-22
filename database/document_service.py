from database.document_store import (
    get_all_documents,
    get_document,
)
from index_hygiene import remove_document_completely


def list_documents():
    return get_all_documents()


def remove_document(document_id):
    return remove_document_completely(document_id)


def get_document_details(document_id):
    return get_document(document_id)
