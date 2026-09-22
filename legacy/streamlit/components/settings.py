"""
Settings page: appearance, AI preferences (frontend-only for now),
document management, and about.
"""

import streamlit as st
from utils import api
from utils.state import get_state, set_state


def render_settings_page():
    st.markdown('<div class="ds-settings-title">Settings</div>', unsafe_allow_html=True)

    _render_appearance_section()
    st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
    _render_ai_settings_section()
    st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
    _render_documents_section()
    st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
    _render_about_section()

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    if st.button("Back to chat"):
        set_state("active_view", "chat")
        st.rerun()


def _render_appearance_section():
    st.markdown('<div class="ds-settings-section-title">Appearance</div>', unsafe_allow_html=True)
    current = get_state("theme_preference")
    choice = st.radio(
        "Theme",
        options=["dark", "light"],
        format_func=lambda v: "Dark mode" if v == "dark" else "Light mode",
        index=0 if current == "dark" else 1,
        horizontal=True,
        label_visibility="collapsed",
        key="theme_radio",
    )
    if choice != current:
        set_state("theme_preference", choice)
        st.rerun()


def _render_ai_settings_section():
    st.markdown('<div class="ds-settings-section-title">AI settings</div>', unsafe_allow_html=True)
    current = get_state("response_length_preference")
    choice = st.radio(
        "Response length",
        options=["normal", "short", "detailed"],
        format_func=lambda v: v.capitalize(),
        index=["normal", "short", "detailed"].index(current),
        horizontal=True,
        key="response_length_radio",
    )
    if choice != current:
        set_state("response_length_preference", choice)
    st.markdown(
        '<div class="ds-settings-note ds-muted">'
        'This preference is saved locally. Response length isn\'t yet supported by the '
        'backend, so answers keep their default behavior until that support is added.'
        '</div>',
        unsafe_allow_html=True,
    )


def _render_documents_section():
    st.markdown('<div class="ds-settings-section-title">Documents</div>', unsafe_allow_html=True)
    documents = get_state("documents")
    st.markdown(
        f'<div class="ds-settings-note ds-muted">{len(documents)} document(s) currently indexed.</div>',
        unsafe_allow_html=True,
    )

    if not documents:
        return

    if not get_state("pending_delete_all"):
        if st.button("Delete all documents", key="delete_all_btn"):
            set_state("pending_delete_all", True)
            st.rerun()
    else:
        st.markdown(
            '<div class="ds-settings-note">This removes every document and its conversation history. This cannot be undone.</div>',
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Confirm delete all", key="confirm_delete_all", type="primary", use_container_width=True):
                _delete_all_documents()
                st.rerun()
        with c2:
            if st.button("Cancel", key="cancel_delete_all", use_container_width=True):
                set_state("pending_delete_all", False)
                st.rerun()


def _delete_all_documents():
    documents = get_state("documents")
    failures = 0
    for doc in documents:
        result = api.delete_document(doc.get("document_id"))
        if not result["ok"]:
            failures += 1

    set_state("chat_history", {})
    set_state("conversation_ids", {})
    set_state("selected_document", None)
    set_state("pending_delete_all", False)

    from components.documents import refresh_documents
    refresh_documents()

    if failures:
        st.toast(f"{failures} document(s) could not be deleted.", icon="⚠️")


def _render_about_section():
    st.markdown('<div class="ds-settings-section-title">About</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="ds-card">
            <div style="font-weight:700;">DocuSage</div>
            <div class="ds-muted" style="font-size:0.85rem; margin-top:0.2rem;">Version 2.0</div>
            <div class="ds-muted" style="font-size:0.85rem; margin-top:0.5rem;">
                Turn your documents into conversations.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


SETTINGS_CSS = """
<style>
.ds-settings-title {
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 1.2rem;
}
.ds-settings-section-title {
    font-size: 0.95rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
}
.ds-settings-note {
    font-size: 0.82rem;
    margin: 0.3rem 0 0.6rem 0;
    line-height: 1.5;
}
</style>
"""
