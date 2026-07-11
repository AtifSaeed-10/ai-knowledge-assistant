import streamlit as st
import requests
from datetime import datetime

# ============================================================
# Configuration (unchanged endpoints / payload contracts)
# ============================================================
BACKEND_URL = "http://127.0.0.1:8000"
UPLOAD_ENDPOINT = f"{BACKEND_URL}/upload"
CHAT_ENDPOINT = f"{BACKEND_URL}/chat"

UPLOAD_TIMEOUT = 60
CHAT_TIMEOUT = 60
CONNECTION_CHECK_TIMEOUT = 3

st.set_page_config(
    page_title="AI Knowledge Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# Light cosmetic styling only (no functional impact)
# ============================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    h1 { font-weight: 700; letter-spacing: -0.02em; }
    h2, h3 { font-weight: 600; }

    .app-subtitle {
        color: #6B7280;
        font-size: 0.95rem;
        margin-top: -0.6rem;
        margin-bottom: 1.4rem;
    }

    section[data-testid="stSidebar"] {
        border-right: 1px solid #E5E7EB;
    }

    div.stButton > button {
        border-radius: 8px;
        font-weight: 500;
    }

    div[data-testid="stChatInput"] textarea {
        border-radius: 10px;
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
# Backend helpers (payloads identical to the original app)
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
        return None, "Could not connect to the backend. Make sure the API server is running."
    except requests.exceptions.Timeout:
        return None, "The upload took too long and timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return None, f"An unexpected error occurred while uploading: {e}"


def send_chat_message(question):
    try:
        response = requests.post(
            CHAT_ENDPOINT,
            json={"question": question},
            timeout=CHAT_TIMEOUT,
        )
        return response, None
    except requests.exceptions.ConnectionError:
        return None, "Could not connect to the backend. Make sure the API server is running."
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
# Sidebar
# ============================================================
with st.sidebar:
    st.markdown("### 🤖 AI Knowledge Assistant")
    st.caption("RAG-powered document Q&A")
    st.divider()

    # ---- System status ----
    st.markdown("**System status**")
    if check_backend_connection():
        st.success("🟢 Backend connected")
    else:
        st.error("🔴 Backend unreachable")
        st.caption(f"Expected API at `{BACKEND_URL}`")

    # LLM provider info -- only shown if the backend has actually returned it
    if st.session_state.last_response_meta:
        provider = st.session_state.last_response_meta.get("provider")
        model = st.session_state.last_response_meta.get("model")
        if provider or model:
            label = provider or "Unknown provider"
            if model:
                label += f" · {model}"
            st.caption(f"🧠 LLM: {label}")

    st.divider()

    # ---- Application info ----
    with st.expander("ℹ️ About this app"):
        st.markdown(
            "This assistant answers questions about your documents using "
            "a Retrieval-Augmented Generation (RAG) pipeline:\n\n"
            "- **Document processing** – extracts and chunks PDF content\n"
            "- **Vector database** – stores embeddings for retrieval\n"
            "- **Retrieval** – finds the most relevant chunks for your question\n"
            "- **LLM generation** – produces an answer grounded in your document"
        )

    # ---- Document upload ----
    st.markdown("**📄 Document**")

    uploaded_file = st.file_uploader(
        "Upload a PDF to add it to the knowledge base",
        type=["pdf"],
        help="The document will be processed and indexed for retrieval.",
    )

    if uploaded_file is not None:
        if uploaded_file.name != st.session_state.last_uploaded_name:
            with st.spinner(f"Uploading and indexing '{uploaded_file.name}'..."):
                response, error = upload_pdf(uploaded_file)

            if error:
                st.error(f"❌ {error}")
            elif response.status_code == 200:
                st.session_state.last_uploaded_name = uploaded_file.name
                st.session_state.upload_meta = safe_json(response)

                st.success(f"✅ '{uploaded_file.name}' uploaded and indexed.")
                st.info("💬 Your document is ready. Start asking questions below.")
            else:
                detail = safe_json(response).get("detail")
                st.error(f"❌ Upload failed (status {response.status_code}).")
                if detail:
                    st.caption(str(detail))
        else:
            st.info(f"📄 '{uploaded_file.name}' is already uploaded.")

    if st.session_state.last_uploaded_name:
        st.caption(f"Active document: **{st.session_state.last_uploaded_name}**")

        # Only display metadata the backend actually returned
        meta = st.session_state.upload_meta or {}
        extra_bits = []
        for key in ("chunks", "num_chunks", "pages", "num_pages"):
            if key in meta:
                extra_bits.append(f"{key.replace('_', ' ')}: {meta[key]}")
        if extra_bits:
            st.caption(" · ".join(extra_bits))
    else:
        st.caption("No document uploaded yet.")

    st.divider()

    # ---- Instructions ----
    with st.expander("❓ How to use"):
        st.markdown(
            "1. Upload a PDF using the uploader above.\n"
            "2. Wait for the confirmation that it was indexed.\n"
            "3. Ask questions about the document in the chat box.\n"
            "4. Use **Clear chat** to start a new conversation."
        )

    st.divider()

    # ---- Chat controls ----
    st.markdown("**Chat**")
    st.caption(f"{len(st.session_state.messages)} messages in this conversation")
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.last_response_meta = None
        st.rerun()


# ============================================================
# Main area
# ============================================================
st.title("🤖 AI Knowledge Assistant")
st.markdown(
    '<p class="app-subtitle">Upload a PDF and ask questions about its content.</p>',
    unsafe_allow_html=True,
)

# ---- Empty states ----
if not st.session_state.messages:
    if st.session_state.last_uploaded_name:
        st.info("Your document is indexed. Ask a question below to get started.")
    else:
        st.info("👋 Upload a PDF from the sidebar, then ask a question about it here.")

# ---- Chat history ----
for message in st.session_state.messages:
    avatar = "🧑" if message["role"] == "user" else "🤖"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("Sources"):
                for s in message["sources"]:
                    st.markdown(f"- {s}")
        if message.get("time"):
            st.caption(message["time"])

# ---- Chat input ----
if prompt := st.chat_input("Ask a question about your document..."):

    user_time = datetime.now().strftime("%H:%M")
    st.session_state.messages.append(
        {"role": "user", "content": prompt, "time": user_time}
    )

    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)
        st.caption(user_time)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            response, error = send_chat_message(prompt)

        answer = "Sorry, I couldn't process that request. Please try again."
        sources = None

        if error:
            st.error(f"❌ {error}")
        elif response.status_code != 200:
            detail = safe_json(response).get("detail")
            st.error(f"❌ Something went wrong (status {response.status_code}).")
            if detail:
                st.caption(str(detail))
        else:
            data = safe_json(response)
            answer = data.get("answer", "No answer was returned by the backend.")
            sources = data.get("sources") or data.get("citations")

            st.markdown(answer)
            if sources:
                with st.expander("Sources"):
                    for s in sources:
                        st.markdown(f"- {s}")

            # Only stored if the backend actually includes this info
            if data.get("provider") or data.get("model"):
                st.session_state.last_response_meta = data

        answer_time = datetime.now().strftime("%H:%M")
        st.caption(answer_time)

    assistant_message = {"role": "assistant", "content": answer, "time": answer_time}
    if sources:
        assistant_message["sources"] = sources

    st.session_state.messages.append(assistant_message)