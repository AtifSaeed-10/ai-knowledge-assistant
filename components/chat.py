"""
Main chat area: empty state (with a working inline upload CTA),
a document-readiness card so the user always knows what they're
talking to, message history restored per document, a status-flow
thinking sequence while waiting on the backend, and citations.
"""

import time
import streamlit as st
from utils import api
from utils.state import (
    get_state,
    set_state,
    get_chat_history,
    append_message,
    get_conversation_id,
)
from components.citations import render_citations, CITATIONS_CSS
from components.status import render_status_flow
from components.sidebar import render_logo
from components.documents import refresh_documents
from components.upload import render_upload_widget

THINKING_STEPS = ["Searching the document", "Understanding context", "Writing the answer"]


def _render_empty_state():
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown('<div class="ds-empty-logo">', unsafe_allow_html=True)
        render_logo(width=64, show_text=False)
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="ds-empty-state">
            <div class="ds-empty-title">Turn your documents into conversations.</div>
            <div class="ds-empty-subtitle">Upload a PDF and DocuSage will read it, understand it,
            and answer your questions with cited sources.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not get_state("show_main_uploader"):
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Upload your first document", key="empty_state_upload_cta",
                         type="primary", use_container_width=True):
                set_state("show_main_uploader", True)
                st.rerun()
    else:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown('<div class="ds-card ds-card-elevated">', unsafe_allow_html=True)
            render_upload_widget(refresh_documents, key_suffix="empty")
            if st.button("Cancel", key="cancel_main_uploader", use_container_width=True):
                set_state("show_main_uploader", False)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)


def _render_document_ready_card(doc, show_prompt):
    filename = doc.get("filename", "Document")
    pages = doc.get("total_pages")
    chunks = doc.get("total_chunks")

    stats = []
    if pages is not None:
        stats.append(f'<div class="ds-ready-stat"><span class="ds-muted">Pages</span><span>{pages}</span></div>')
    if chunks is not None:
        stats.append(f'<div class="ds-ready-stat"><span class="ds-muted">Chunks</span><span>{chunks}</span></div>')

    st.markdown(
        f"""
        <div class="ds-ready-card">
            <div class="ds-ready-row">
                <div class="ds-ready-filename">{filename}</div>
                <div class="ds-ready-pill">&#10003; Ready</div>
            </div>
            <div class="ds-ready-stats">{''.join(stats)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if show_prompt:
        st.markdown(
            '<div class="ds-ready-prompt">Ask anything about this document.</div>',
            unsafe_allow_html=True,
        )


def _render_message(message):
    role = message["role"]
    content = message["content"]

    if role == "user":
        st.markdown(
            f"""
            <div class="ds-msg-row ds-msg-row-user">
                <div class="ds-msg-bubble ds-msg-user">{content}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="ds-msg-row ds-msg-row-ai">
                <div class="ds-msg-ai">{content}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        sources = message.get("sources")
        if sources:
            render_citations(sources)


def render_chat_area():
    st.markdown(CITATIONS_CSS, unsafe_allow_html=True)
    st.markdown(CHAT_CSS, unsafe_allow_html=True)

    selected = get_state("selected_document")

    if not selected:
        _render_empty_state()
        return

    document_id = selected.get("document_id")
    history = get_chat_history(document_id)

    _render_document_ready_card(selected, show_prompt=not history)

    chat_container = st.container()
    with chat_container:
        for message in history:
            _render_message(message)

    if get_state("backend_unavailable"):
        st.warning(api.UNAVAILABLE_ERROR)

    question = st.chat_input("Ask a question about this document")
    if question:
        append_message(document_id, "user", question)
        st.rerun()

    # After a rerun that just added a user message with no matching AI
    # reply yet, fetch the answer. This two-phase pattern lets the user
    # bubble render immediately, before the (blocking) API call.
    if history and history[-1]["role"] == "user":
        flow_placeholder = st.empty()
        for i in range(len(THINKING_STEPS)):
            render_status_flow(flow_placeholder, THINKING_STEPS, active_index=i)
            if i < len(THINKING_STEPS) - 1:
                time.sleep(0.5)

        result = api.send_chat_message(
            question=history[-1]["content"],
            document_id=document_id,
            conversation_id=get_conversation_id(document_id),
            response_length=get_state("response_length_preference"),
        )

        flow_placeholder.empty()

        if result["ok"]:
            data = result["data"]
            answer = data.get("answer", "")
            sources = data.get("sources", [])
            append_message(document_id, "assistant", answer, sources=sources)
            set_state("backend_unavailable", False)
        else:
            set_state("backend_unavailable", result.get("kind") == "unavailable")
            append_message(document_id, "assistant", result["error"])

        st.rerun()


CHAT_CSS = """
<style>
.ds-empty-state {
    text-align: center;
    padding: 0.5rem 1rem 1.5rem 1rem;
}
.ds-empty-logo {
    display: flex;
    justify-content: center;
    padding-top: 2rem;
}
.ds-empty-title {
    font-size: 1.7rem;
    font-weight: 700;
    color: var(--text-main);
    margin-bottom: 0.6rem;
    letter-spacing: -0.02em;
}
.ds-empty-subtitle {
    font-size: 0.95rem;
    color: var(--text-muted);
    max-width: 460px;
    margin: 0 auto;
    line-height: 1.5;
}
.ds-ready-card {
    background-color: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 14px;
    padding: 0.85rem 1.05rem;
    margin-bottom: 1rem;
    box-shadow: var(--shadow-sm);
}
.ds-ready-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.ds-ready-filename {
    font-weight: 700;
    font-size: 1rem;
    color: var(--text-main);
}
.ds-ready-pill {
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--accent-olive);
    background-color: var(--accent-sage-subtle);
    border-radius: 20px;
    padding: 0.2rem 0.65rem;
    white-space: nowrap;
}
.ds-ready-stats {
    display: flex;
    gap: 1.4rem;
    margin-top: 0.5rem;
}
.ds-ready-stat {
    display: flex;
    flex-direction: column;
    font-size: 0.8rem;
}
.ds-ready-stat span:last-child {
    font-weight: 600;
    color: var(--text-main);
}
.ds-ready-prompt {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin: -0.3rem 0 1rem 0.15rem;
}
.ds-msg-row {
    display: flex;
    margin-bottom: 0.9rem;
}
.ds-msg-row-user { justify-content: flex-end; }
.ds-msg-row-ai { justify-content: flex-start; }
.ds-msg-bubble.ds-msg-user {
    background-color: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 14px 14px 4px 14px;
    padding: 0.65rem 0.95rem;
    max-width: 70%;
    box-shadow: var(--shadow-sm);
    font-size: 0.92rem;
}
.ds-msg-ai {
    max-width: 85%;
    padding: 0.2rem 0.1rem;
    font-size: 0.95rem;
    line-height: 1.6;
    color: var(--text-main);
}
</style>
"""
