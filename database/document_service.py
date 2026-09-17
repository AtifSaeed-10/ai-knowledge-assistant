from database.document_store import (
    get_all_documents,
    get_document,
    get_documents_for_owner,
)
from index_hygiene import remove_document_completely


def list_documents(owner_type=None, owner_id=None):
    """Library listing. Scoped to one actor when an owner is supplied."""
    if owner_type and owner_id:
        return get_documents_for_owner(owner_type, owner_id)
    return get_all_documents()


def remove_document(document_id):
    return remove_document_completely(document_id)


def get_document_details(document_id):
    return get_document(document_id)
