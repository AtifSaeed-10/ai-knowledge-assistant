import streamlit as st
import streamlit.components.v1 as components
import requests
import os
import json
import html as html_utils
from datetime import datetime
import uuid

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())

# ============================================================
# Configuration (unchanged endpoints / payload contracts)
# ============================================================
BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://127.0.0.1:8000"
)
UPLOAD_ENDPOINT = f"{BACKEND_URL}/upload"
CHAT_ENDPOINT = f"{BACKEND_URL}/chat"

UPLOAD_TIMEOUT = 300
CHAT_TIMEOUT = 60
CONNECTION_CHECK_TIMEOUT = 3

st.set_page_config(
    page_title="AI Knowledge Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# Design system: CSS variables + component styles.
# Purely cosmetic -- no functional impact on the app logic below.
# ============================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --text: var(--text-color);
    --muted: rgba(128,128,128,0.8);
    --border: var(--border-color);
    --card-bg: var(--secondary-background-color);
    --sidebar-bg: var(--secondary-background-color);
    --accent: var(--primary-color);

    --accent-soft: rgba(79,70,229,0.12);

    --ok-bg: rgba(16,185,129,0.12);
    --ok-text: #059669;

    --error-bg: rgba(239,68,68,0.12);
    --error-text: #DC2626;
}

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: var(--text);
    }

    h1 { font-weight: 700; letter-spacing: -0.02em; }
    h2, h3 { font-weight: 600; }

    .app-subtitle {
        color: var(--muted);
        font-size: 0.95rem;
        margin-top: -0.6rem;
        margin-bottom: 1.2rem;
    }

    /* ---- Sidebar shell ---- */
    section[data-testid="stSidebar"] {
        border-right: 1px solid var(--border);
        background: var(--sidebar-bg);
    }
    .sidebar-brand {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 2px;
    }
    .sidebar-brand-icon {
        font-size: 1.4rem;
    }
    .sidebar-brand-title {
        font-weight: 700;
        font-size: 1.05rem;
        line-height: 1.1;
    }
    .sidebar-brand-caption {
        color: var(--muted);
        font-size: 0.8rem;
        margin-top: 2px;
        margin-bottom: 0.6rem;
    }
    .section-label {
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--muted);
        margin: 0.4rem 0 0.5rem 0;
    }

    /* ---- Status badges ---- */
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    .status-badge-ok { background: var(--secondary-background-color); color: var(--ok-text); }
    .status-badge-error { background: var(--error-bg); color: var(--error-text); }

    /* ---- Cards ---- */
    .card {
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 12px 14px;
        background: var(--card-bg);
        margin-bottom: 10px;
    }
    .doc-card {
        display: flex;
        gap: 10px;
        align-items: flex-start;
    }
    .doc-card-icon { font-size: 1.3rem; line-height: 1.3; }
    .doc-card-name {
        font-weight: 600;
        font-size: 0.88rem;
        word-break: break-word;
    }
    .doc-card-meta {
        font-size: 0.75rem;
        color: var(--muted);
        margin-top: 4px;
    }
    .doc-card-empty {
        color: var(--muted);
        font-size: 0.85rem;
    }

    .stat-row {
        display: flex;
        justify-content: space-between;
        font-size: 0.82rem;
        color: var(--muted);
        padding: 3px 0;
    }
    .stat-row b { color: var(--text); font-weight: 600; }

    /* ---- Citations ---- */
    .source-card {
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 10px 12px;
        margin-bottom: 8px;
        background: var(--card-bg);
    }
    .source-card-title {
        font-weight: 600;
        font-size: 0.82rem;
        margin-bottom: 4px;
        color: var(--accent);
    }
    .source-card-row {
        font-size: 0.8rem;
        color: var(--muted);
        display: flex;
        justify-content: space-between;
        padding: 1px 0;
    }
    .source-card-row b { color: var(--text); }

    /* ---- Chat area ---- */
    [data-testid="stChatMessage"] {
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 10px;
        background: var(--card-bg);
    }
    div[data-testid="stChatInput"] textarea {
        border-radius: 10px;
    }
    .msg-time {
        font-size: 0.72rem;
        color: var(--muted);
        margin-top: 2px;
    }

    /* ---- Empty state ---- */
    .empty-state {
        text-align: center;
        padding: 56px 20px;
        color: var(--muted);
        border: 1px dashed var(--border);
        border-radius: 14px;
        margin-top: 16px;
    }
    .empty-state-icon { font-size: 2rem; margin-bottom: 10px; }
    .empty-state-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: var(--text);
        margin-bottom: 6px;
    }
    .empty-state-sub { font-size: 0.88rem; }

    div.stButton > button {
        border-radius: 8px;
        font-weight: 500;
    }
    div.stDownloadButton > button {
        border-radius: 8px;
        font-weight: 500;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# Session state
# ============================================================
if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_uploaded_name" not in st.session_state:
    st.session_state.last_uploaded_name = None

if "upload_meta" not in st.session_state:
    st.session_state.upload_meta = None

if "last_response_meta" not in st.session_state:
    st.session_state.last_response_meta = None


# ============================================================
# Backend helpers (payloads identical to the original app --
# same endpoints, same request bodies, same error handling)
# ============================================================
@st.cache_data(ttl=15, show_spinner=False)
def check_backend_connection():
    """Lightweight reachability check. Any HTTP response counts as
    'connected' -- only network-level failures count as disconnected."""
    try:
        requests.get(BACKEND_URL, timeout=CONNECTION_CHECK_TIMEOUT)
        return True
    except requests.exceptions.RequestException:
        return False


def upload_pdf(file):
    try:
        response = requests.post(
            UPLOAD_ENDPOINT,
            files={
                "file": (
                    file.name,
                    file.getvalue(),
                    "application/pdf",
                )
            },
            timeout=UPLOAD_TIMEOUT,
        )
        return response, None
    except requests.exceptions.ConnectionError:
        return None, "Unable to connect to the AI backend. Please make sure the server is running."
    except requests.exceptions.Timeout:
        return None, "The upload took too long and timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return None, f"An unexpected error occurred while uploading: {e}"


def send_chat_message(question):
    try:
        response = requests.post(
            CHAT_ENDPOINT,
            json={"question": question,"conversation_id": st.session_state.conversation_id},
            timeout=CHAT_TIMEOUT,
        )
        return response, None
    except requests.exceptions.ConnectionError:
        return None, "Unable to connect to the AI backend. Please make sure the server is running."
    except requests.exceptions.Timeout:
        return None, "The request took too long and timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return None, f"An unexpected error occurred: {e}"


def safe_json(response):
    try:
        return response.json()
    except ValueError:
        return {}


# ============================================================
# UI helpers (new -- purely presentational, no backend impact)
# ============================================================
def render_status_badge(connected: bool) -> str:
    """Small pill badge for the backend connection state."""
    if connected:
        return '<span class="status-badge status-badge-ok">● Connected</span>'
    return '<span class="status-badge status-badge-error">● Disconnected</span>'


def relevance_from_distance(distance):
    """Converts a vector distance into a friendly 0-100% relevance score."""
    if not isinstance(distance, (int, float)):
        return None
    pct = round((1 - distance) * 100)
    return max(0, min(100, pct))


def render_source_card_html(source, index: int) -> str:
    """Builds one citation card. Supports the structured backend format
    ({page, chunk_id, distance}) and falls back gracefully to plain-text
    sources for backward compatibility."""
    if isinstance(source, dict):
        page = html_utils.escape(str(source.get("page", "—")))
        chunk_id = html_utils.escape(str(source.get("chunk_id", source.get("chunk", "—"))))
        relevance = relevance_from_distance(source.get("distance"))
        relevance_str = f"{relevance}%" if relevance is not None else "—"
        return f"""
        <div class="source-card">
            <div class="source-card-title">Source {index}</div>
            <div class="source-card-row"><span>Page</span><b>{page}</b></div>
            <div class="source-card-row"><span>Chunk</span><b>{chunk_id}</b></div>
            <div class="source-card-row"><span>Relevance</span><b>{relevance_str}</b></div>
        </div>
        """
    return f"""
    <div class="source-card">
        <div class="source-card-title">Source {index}</div>
        <div class="source-card-row"><span>{html_utils.escape(str(source))}</span></div>
    </div>
    """


def render_sources_section(sources):
    """Renders a collapsible 'Sources' expander with citation cards."""
    if not sources:
        return
    with st.expander(f"Sources ({len(sources)})", expanded=False):
        cards_html = "".join(
            render_source_card_html(s, i) for i, s in enumerate(sources, start=1)
        )
        st.markdown(cards_html, unsafe_allow_html=True)


def render_copy_button(text: str, key: str):
    """Small embedded copy-to-clipboard control for assistant answers.
    Implemented as a tiny HTML/JS snippet since Streamlit has no native
    clipboard widget -- no extra Python packages required."""
    safe_text = json.dumps(text)
    components.html(
        f"""
        <div style="display:flex; justify-content:flex-end; align-items:center;">
          <button id="copy-btn-{key}"
            style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:6px;
                   padding:3px 10px;font-size:12px;color:#6B7280;cursor:pointer;
                   font-family:Inter,sans-serif;">
            Copy
          </button>
          <span id="copied-{key}" style="opacity:0;transition:opacity .25s;
                font-size:12px;color:#059669;margin-left:6px;
                font-family:Inter,sans-serif;">Copied</span>
        </div>
        <script>
          const btn = document.getElementById("copy-btn-{key}");
          const msg = document.getElementById("copied-{key}");
          btn.addEventListener("click", function() {{
            navigator.clipboard.writeText({safe_text});
            msg.style.opacity = 1;
            setTimeout(() => {{ msg.style.opacity = 0; }}, 1200);
          }});
        </script>
        """,
        height=34,
    )


def build_conversation_export() -> str:
    """Builds a Markdown export of the full conversation, including sources."""
    lines = [
        "# AI Knowledge Assistant — Conversation Export",
        f"_Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
    ]
    if st.session_state.last_uploaded_name:
        lines.append(f"_Document: {st.session_state.last_uploaded_name}_")
    lines.append("\n---\n")

    for message in st.session_state.messages:
        speaker = "You" if message["role"] == "user" else "Assistant"
        timestamp = message.get("time", "")
        lines.append(f"### {speaker} ({timestamp})")
        lines.append(message["content"])

        sources = message.get("sources")
        if sources:
            lines.append("\n**Sources:**")
            for i, s in enumerate(sources, start=1):
                if isinstance(s, dict):
                    page = s.get("page", "—")
                    chunk_id = s.get("chunk_id", "—")
                    relevance = relevance_from_distance(s.get("distance"))
                    relevance_str = f"{relevance}%" if relevance is not None else "—"
                    lines.append(f"- Source {i}: Page {page}, Chunk {chunk_id}, Relevance {relevance_str}")
                else:
                    lines.append(f"- {s}")
        lines.append("\n---\n")

    return "\n".join(lines)


# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-icon">🤖</div>
            <div class="sidebar-brand-title">AI Knowledge Assistant</div>
        </div>
        <div class="sidebar-brand-caption">RAG-powered document Q&A</div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    # ---- System status ----
    st.markdown('<div class="section-label">System status</div>', unsafe_allow_html=True)
    is_connected = check_backend_connection()
    st.markdown(render_status_badge(is_connected), unsafe_allow_html=True)
    if not is_connected:
        st.caption(f"Expected API at `{BACKEND_URL}`")

    # LLM provider info -- only shown if the backend has actually returned it
    if st.session_state.last_response_meta:
        provider = st.session_state.last_response_meta.get("provider")
        model = st.session_state.last_response_meta.get("model")
        if provider or model:
            label = provider or "Unknown provider"
            if model:
                label += f" · {model}"
            st.caption(f"🧠 {label}")

    st.divider()

    # ---- Application info ----
    with st.expander("About this app"):
        st.markdown(
            "This assistant answers questions about your documents using "
            "a Retrieval-Augmented Generation (RAG) pipeline:\n\n"
            "- **Document processing** – extracts and chunks PDF content\n"
            "- **Vector database** – stores embeddings for retrieval\n"
            "- **Retrieval** – finds the most relevant chunks for your question\n"
            "- **LLM generation** – produces an answer grounded in your document"
        )

    # ---- Document upload ----
    st.markdown('<div class="section-label">Document</div>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Upload a PDF to add it to the knowledge base",
        type=["pdf"],
        help="The document will be processed and indexed for retrieval.",
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        if uploaded_file.name != st.session_state.last_uploaded_name:
            with st.spinner(f"Processing '{uploaded_file.name}'. "
                    "Large documents may take a few minutes..."
                            ):
                response, error = upload_pdf(uploaded_file)

            if error:
                st.error(error)
            elif response.status_code == 200:
                st.session_state.last_uploaded_name = uploaded_file.name
                st.session_state.upload_meta = safe_json(response)

                st.success(f"'{uploaded_file.name}' uploaded and indexed.")
                st.info("Your document is ready. Start asking questions below.")
            else:
                detail = safe_json(response).get("detail")
                st.error(f"Upload failed (status {response.status_code}).")
                if detail:
                    st.caption(str(detail))
        else:
            st.info(f"'{uploaded_file.name}' is already uploaded.")

    # ---- Document card ----
    if st.session_state.last_uploaded_name:
        meta = st.session_state.upload_meta or {}
        meta_bits = []
        for key in ("chunks", "num_chunks", "pages", "num_pages"):
            if key in meta:
                meta_bits.append(f"{key.replace('_', ' ').title()}: {meta[key]}")
        meta_html = (
            f'<div class="doc-card-meta">{" · ".join(meta_bits)}</div>' if meta_bits else ""
        )
        st.markdown(
            f"""
            <div class="card doc-card">
                <div class="doc-card-icon">📄</div>
                <div>
                    <div class="doc-card-name">{html_utils.escape(st.session_state.last_uploaded_name)}</div>
                    <span class="status-badge status-badge-ok">✓ Indexed</span>
                    {meta_html}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="card doc-card-empty">No document uploaded yet.</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ---- Instructions ----
    with st.expander("How to use"):
        st.markdown(
            "1. Upload a PDF using the uploader above.\n"
            "2. Wait for the confirmation that it was indexed.\n"
            "3. Ask questions about the document in the chat box.\n"
            "4. Use **Clear chat** to start a new conversation."
        )

    st.divider()

    # ---- Session stats ----
    st.markdown('<div class="section-label">Session stats</div>', unsafe_allow_html=True)
    question_count = sum(1 for m in st.session_state.messages if m["role"] == "user")
    active_doc = st.session_state.last_uploaded_name or "None"
    st.markdown(
        f"""
        <div class="card">
            <div class="stat-row"><span>Questions asked</span><b>{question_count}</b></div>
            <div class="stat-row"><span>Total messages</span><b>{len(st.session_state.messages)}</b></div>
            <div class="stat-row"><span>Active document</span><b>{html_utils.escape(active_doc)}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Chat controls ----
    st.markdown('<div class="section-label">Chat</div>', unsafe_allow_html=True)
    col_clear, col_export = st.columns(2)
    with col_clear:
        if st.button("Clear", use_container_width=True):
            st.session_state.messages = []
            st.session_state.last_response_meta = None
            st.rerun()
    with col_export:
        st.download_button(
            "Export",
            data=build_conversation_export(),
            file_name=f"conversation_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown",
            use_container_width=True,
            disabled=not st.session_state.messages,
        )


# ============================================================
# Main area
# ============================================================
st.title("AI Knowledge Assistant")
st.markdown(
    '<p class="app-subtitle">Upload a PDF and ask questions about its content.</p>',
    unsafe_allow_html=True,
)

# ---- Empty states ----
if not st.session_state.messages:
    if st.session_state.last_uploaded_name:
        st.markdown(
            """
            <div class="empty-state">
                <div class="empty-state-icon">💬</div>
                <div class="empty-state-title">Ask something about your document</div>
                <div class="empty-state-sub">Your document is indexed and ready. Try asking a question below.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="empty-state">
                <div class="empty-state-icon">📄</div>
                <div class="empty-state-title">Upload a document to get started</div>
                <div class="empty-state-sub">Add a PDF from the sidebar, then ask questions about its content here.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---- Chat history ----
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_copy_button(message["content"], key=f"hist-{idx}")
        if message.get("sources"):
            render_sources_section(message["sources"])
        if message.get("time"):
            st.markdown(f'<div class="msg-time">{message["time"]}</div>', unsafe_allow_html=True)

# ---- Chat input ----
if prompt := st.chat_input("Ask a question about your document..."):

    user_time = datetime.now().strftime("%H:%M")
    st.session_state.messages.append(
        {"role": "user", "content": prompt, "time": user_time}
    )

    with st.chat_message("user"):
        st.markdown(prompt)
        st.markdown(f'<div class="msg-time">{user_time}</div>', unsafe_allow_html=True)

    with st.chat_message("assistant"):
        with st.spinner("Generating answer..."):
            response, error = send_chat_message(prompt)

        answer = "Sorry, I couldn't process that request. Please try again."
        sources = None

        if error:
            st.error(error)
        elif response.status_code != 200:
            detail = safe_json(response).get("detail")
            st.error(f"Something went wrong (status {response.status_code}).")
            if detail:
                st.caption(str(detail))
        else:
            data = safe_json(response)
            answer = data.get("answer", "No answer was returned by the backend.")
            sources = data.get("sources") or data.get("citations")

            st.markdown(answer)
            render_copy_button(answer, key=f"live-{len(st.session_state.messages)}")
            render_sources_section(sources)

            # Only stored if the backend actually includes this info
            if data.get("provider") or data.get("model"):
                st.session_state.last_response_meta = data

        answer_time = datetime.now().strftime("%H:%M")
        st.markdown(f'<div class="msg-time">{answer_time}</div>', unsafe_allow_html=True)

    assistant_message = {"role": "assistant", "content": answer, "time": answer_time}
    if sources:
        assistant_message["sources"] = sources

    st.session_state.messages.append(assistant_message)