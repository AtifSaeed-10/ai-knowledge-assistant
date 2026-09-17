"""
Upload experience — turns a file upload into a document-to-knowledge
narrative using a real status checklist (no fake percentages, no
default Streamlit "drag and drop" look left unstyled).

Flow: Uploading document -> Processing document -> Building knowledge
base -> Ready.
"""

import time
import streamlit as st
from utils import api
from utils.state import set_state, get_state
from components.status import render_status_flow

STEPS = [
    "Uploading document",
    "Processing document",
    "Building knowledge base",
    "Ready",
]


def _run_upload(uploaded_file, refresh_documents_fn, flow_placeholder):
    # Step 0: uploading — paint immediately so there's never a blank gap
    # between the user picking a file and seeing feedback.
    set_state("upload_status", "uploading")
    render_status_flow(flow_placeholder, STEPS, active_index=0)
    time.sleep(0.4)

    # Step 1: processing (extraction/chunking) — shown before the network
    # call so the user isn't staring at "Uploading" while the request is
    # actually already in flight.
    set_state("upload_status", "processing")
    render_status_flow(flow_placeholder, STEPS, active_index=1)
    time.sleep(0.4)

    # Step 2: this is where the real (blocking) work happens server-side —
    # chunking, embedding, and indexing all occur inside this one call.
    set_state("upload_status", "indexing")
    render_status_flow(flow_placeholder, STEPS, active_index=2)
    result = api.upload_document(uploaded_file.getvalue(), uploaded_file.name)

    if not result["ok"]:
        set_state("upload_status", "error")
        set_state("upload_error", result["error"])
        render_status_flow(flow_placeholder, STEPS, active_index=2, error_index=2)
        st.error(result["error"])
        return None

    # Step 3: ready
    set_state("upload_status", "ready")
    render_status_flow(flow_placeholder, STEPS, active_index=len(STEPS))
    time.sleep(0.35)

    data = result["data"]
    document = {
        "document_id": data.get("document_id"),
        "filename": data.get("filename", uploaded_file.name),
        "total_pages": data.get("pages"),
        "total_chunks": data.get("chunks"),
    }

    refresh_documents_fn()
    set_state("selected_document", document)
    set_state("active_view", "chat")
    set_state("show_main_uploader", False)
    return document


def render_upload_widget(refresh_documents_fn, key_suffix=""):
    """
    Renders the upload card. `refresh_documents_fn` should call
    GET /documents and update state — passed in so this component
    never has to know about documents.py internals.
    """
    st.markdown(
        """
        <div class="ds-upload-caption">
            <span class="ds-upload-caption-title">Add a document</span>
            <span class="ds-upload-caption-sub">PDF, up to a few hundred pages</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "Upload a PDF",
        type=["pdf"],
        label_visibility="collapsed",
        key=f"uploader_{key_suffix}",
    )

    flow_placeholder = st.empty()

    if uploaded_file is not None:
        last_processed = get_state("last_uploaded_filename")
        if last_processed != uploaded_file.name:
            set_state("last_uploaded_filename", uploaded_file.name)
            _run_upload(uploaded_file, refresh_documents_fn, flow_placeholder)
            st.rerun()


UPLOAD_CSS = """
<style>
.ds-upload-caption {
    display: flex;
    flex-direction: column;
    margin-bottom: 0.35rem;
}
.ds-upload-caption-title {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text-main);
}
.ds-upload-caption-sub {
    font-size: 0.72rem;
    color: var(--text-muted);
}
</style>
"""
