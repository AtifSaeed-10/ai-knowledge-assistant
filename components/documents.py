"""
Document library: list, select, delete. Also renders the optional
right-hand document info panel (hidden by default, opened on demand).
"""

import streamlit as st
from utils import api
from utils.state import get_state, set_state, clear_document_data


def refresh_documents():
    result = api.list_documents()
    if result["ok"]:
        set_state("documents", result["data"] or [])
        set_state("documents_loaded", True)
        set_state("backend_unavailable", False)
    else:
        set_state("backend_unavailable", result.get("kind") == "unavailable")
        set_state("last_error", result["error"])


def _select_document(doc):
    set_state("selected_document", doc)
    set_state("active_view", "chat")
    set_state(f"confirm_delete_{doc.get('document_id')}", False)


def _delete_document(document_id):
    result = api.delete_document(document_id)
    if not result["ok"]:
        st.toast(result["error"], icon="⚠️")
        return

    clear_document_data(document_id)

    selected = get_state("selected_document")
    if selected and selected.get("document_id") == document_id:
        set_state("selected_document", None)

    set_state(f"confirm_delete_{document_id}", False)
    refresh_documents()


def render_document_library():
    documents = get_state("documents")

    st.markdown('<div class="ds-section-label">Library</div>', unsafe_allow_html=True)

    if get_state("backend_unavailable"):
        st.markdown(
            '<div class="ds-empty-note">Can\'t reach the server right now.</div>',
            unsafe_allow_html=True,
        )
        return

    if not documents:
        st.markdown(
            '<div class="ds-empty-note">No documents yet. Upload one to get started.</div>',
            unsafe_allow_html=True,
        )
        return

    selected = get_state("selected_document")
    selected_id = selected.get("document_id") if selected else None

    for doc in documents:
        doc_id = doc.get("document_id")
        filename = doc.get("filename", "Untitled document")
        is_active = doc_id == selected_id
        confirming = get_state(f"confirm_delete_{doc_id}")

        card_class = "ds-doc-card ds-doc-card-active" if is_active else "ds-doc-card"
        st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)

        col_main, col_del = st.columns([5, 1])
        with col_main:
            if st.button(filename, key=f"select_{doc_id}", use_container_width=True):
                _select_document(doc)
                st.rerun()
            pages = doc.get("total_pages")
            if pages is not None:
                st.markdown(
                    f'<div class="ds-doc-meta">{pages} pages</div>',
                    unsafe_allow_html=True,
                )
        with col_del:
            if not confirming:
                if st.button("Delete", key=f"del_{doc_id}", use_container_width=True):
                    set_state(f"confirm_delete_{doc_id}", True)
                    st.rerun()

        if confirming:
            st.markdown(
                '<div class="ds-confirm-text">Delete this document and its conversation?</div>',
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Confirm", key=f"confirm_{doc_id}", type="primary", use_container_width=True):
                    _delete_document(doc_id)
                    st.rerun()
            with c2:
                if st.button("Cancel", key=f"cancel_{doc_id}", use_container_width=True):
                    set_state(f"confirm_delete_{doc_id}", False)
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


def render_document_info_panel():
    """Optional right panel — only rendered when the user opts in."""
    doc = get_state("selected_document")
    if not doc:
        return

    st.markdown('<div class="ds-info-panel-title">Document details</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="ds-card">
            <div class="ds-info-row"><span class="ds-muted">Filename</span><span>{doc.get('filename', '—')}</span></div>
            <div class="ds-info-row"><span class="ds-muted">Pages</span><span>{doc.get('total_pages', '—')}</span></div>
            <div class="ds-info-row"><span class="ds-muted">Chunks</span><span>{doc.get('total_chunks', '—')}</span></div>
            <div class="ds-info-row"><span class="ds-muted">Uploaded</span><span>{doc.get('upload_time', '—')}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


DOCUMENTS_CSS = """
<style>
.ds-section-label {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-muted);
    margin: 1.1rem 0 0.5rem 0;
}
.ds-empty-note {
    font-size: 0.85rem;
    color: var(--text-muted);
    padding: 0.6rem 0;
}
.ds-doc-card {
    background-color: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 0.4rem 0.5rem 0.2rem 0.5rem;
    margin-bottom: 0.5rem;
}
.ds-doc-card-active {
    border-color: var(--accent-olive);
    box-shadow: var(--shadow-glow);
}
.ds-doc-meta {
    font-size: 0.72rem;
    color: var(--text-muted);
    padding: 0 0.3rem 0.4rem 0.3rem;
}
.ds-confirm-text {
    font-size: 0.78rem;
    color: var(--text-muted);
    padding: 0.3rem;
}
.ds-info-panel-title {
    font-weight: 700;
    font-size: 0.95rem;
    margin-bottom: 0.6rem;
}
.ds-info-row {
    display: flex;
    justify-content: space-between;
    padding: 0.35rem 0;
    border-bottom: 1px solid var(--border-subtle);
    font-size: 0.85rem;
}
.ds-info-row:last-child { border-bottom: none; }
</style>
"""
