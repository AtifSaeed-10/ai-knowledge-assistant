"""
Centralized session_state management for DocuSage.

Every key the app reads or writes lives here. Components should use
get_state()/set_state() rather than touching st.session_state directly,
so behavior (defaults, validation, future logging) stays in one place.
"""

import streamlit as st

DEFAULTS = {
    # Documents
    "documents": [],                 # cached GET /documents result
    "selected_document": None,       # dict: currently active document
    "documents_loaded": False,       # whether we've fetched at least once

    # Conversations — keyed per document_id so switching documents
    # restores prior context instead of discarding it.
    "conversation_ids": {},          # {document_id: conversation_id}
    "chat_history": {},              # {document_id: [ {role, content, sources?} ]}

    # Upload
    "upload_status": "idle",         # idle | uploading | processing | indexing | ready | error
    "upload_error": None,

    # Navigation / layout
    "active_view": "chat",           # chat | settings
    "show_info_panel": False,        # right panel is opt-in, hidden by default

    # Preferences
    "theme_preference": "dark",      # dark | light
    "response_length_preference": "normal",  # normal | short | detailed (frontend-only for now)

    # Reserved for a future developer mode that surfaces retrieval
    # debugging info (distance, chunk_id, etc). Not exposed in the UI
    # yet — kept here so citations.py / chat.py already have a single
    # flag to branch on when it ships.
    "developer_mode": False,

    # Errors / connectivity
    "last_error": None,
    "backend_unavailable": False,

    # Transient UI flags (delete confirmations, etc.)
    "pending_delete_id": None,
    "pending_delete_all": False,
    "last_uploaded_filename": None,
    "show_main_uploader": False,
}


def init_state():
    """Populate any missing keys with their defaults. Safe to call every rerun."""
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            # Use a fresh copy for mutable defaults (list/dict)
            st.session_state[key] = value.copy() if isinstance(value, (list, dict)) else value


def get_state(key):
    return st.session_state.get(key, DEFAULTS.get(key))


def set_state(key, value):
    st.session_state[key] = value


def get_chat_history(document_id):
    if not document_id:
        return []
    return st.session_state["chat_history"].get(document_id, [])


def append_message(document_id, role, content, sources=None):
    if document_id not in st.session_state["chat_history"]:
        st.session_state["chat_history"][document_id] = []
    message = {"role": role, "content": content}
    if sources is not None:
        message["sources"] = sources
    st.session_state["chat_history"][document_id].append(message)


def get_conversation_id(document_id):
    if not document_id:
        return None
    return st.session_state["conversation_ids"].get(document_id)


def set_conversation_id(document_id, conversation_id):
    st.session_state["conversation_ids"][document_id] = conversation_id


def clear_document_data(document_id):
    """Used when a document is deleted — remove its chat history/conversation."""
    st.session_state["chat_history"].pop(document_id, None)
    st.session_state["conversation_ids"].pop(document_id, None)
