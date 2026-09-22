"""
All backend communication lives here. No other module should import
`requests` directly — this keeps error handling, timeouts, and the
base URL in exactly one place.

Every function returns a normalized dict:
    {"ok": True,  "data": <parsed json>}
    {"ok": False, "error": "<user-safe message>"}

Callers never see raw exceptions, status codes, or tracebacks —
those are only used internally to pick the right user-safe message.
"""

import requests

BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = 15          # seconds, for regular JSON calls
UPLOAD_TIMEOUT = 120          # seconds, uploads can take longer to index

GENERIC_ERROR = "Something went wrong while processing your request. Please try again."
UNAVAILABLE_ERROR = "DocuSage can't reach the server right now. Please check your connection and try again."
TIMEOUT_ERROR = "This is taking longer than expected. Please try again in a moment."


def _handle_exception(exc):
    if isinstance(exc, requests.exceptions.ConnectionError):
        return {"ok": False, "error": UNAVAILABLE_ERROR, "kind": "unavailable"}
    if isinstance(exc, requests.exceptions.Timeout):
        return {"ok": False, "error": TIMEOUT_ERROR, "kind": "timeout"}
    return {"ok": False, "error": GENERIC_ERROR, "kind": "unknown"}


def _handle_response(response):
    try:
        if response.status_code >= 200 and response.status_code < 300:
            # Some endpoints (e.g. DELETE) may return no body
            if not response.content:
                return {"ok": True, "data": None}
            return {"ok": True, "data": response.json()}
        return {"ok": False, "error": GENERIC_ERROR, "kind": "http_error"}
    except ValueError:
        return {"ok": False, "error": GENERIC_ERROR, "kind": "parse_error"}


def upload_document(file_bytes, filename):
    """POST /upload — multipart form upload."""
    try:
        files = {"file": (filename, file_bytes, "application/pdf")}
        response = requests.post(f"{BASE_URL}/upload", files=files, timeout=UPLOAD_TIMEOUT)
        return _handle_response(response)
    except requests.exceptions.RequestException as exc:
        return _handle_exception(exc)


def list_documents():
    """GET /documents"""
    try:
        response = requests.get(f"{BASE_URL}/documents", timeout=DEFAULT_TIMEOUT)
        return _handle_response(response)
    except requests.exceptions.RequestException as exc:
        return _handle_exception(exc)


def get_document(document_id):
    """GET /documents/{document_id}"""
    try:
        response = requests.get(f"{BASE_URL}/documents/{document_id}", timeout=DEFAULT_TIMEOUT)
        return _handle_response(response)
    except requests.exceptions.RequestException as exc:
        return _handle_exception(exc)


def delete_document(document_id):
    """DELETE /documents/{document_id}"""
    try:
        response = requests.delete(f"{BASE_URL}/documents/{document_id}", timeout=DEFAULT_TIMEOUT)
        return _handle_response(response)
    except requests.exceptions.RequestException as exc:
        return _handle_exception(exc)


def send_chat_message(question, document_id, conversation_id, response_length="normal"):
    """
    POST /chat

    NOTE: `response_length` is accepted here so the calling code
    (chat.py) never needs to change when the backend adds support for
    it. Today it is intentionally NOT included in the payload, since
    the current /chat API only accepts question/document_id/
    conversation_id. When the backend adds support, uncomment the
    marked line below — no other file needs to change.
    """
    try:
        payload = {
            "question": question,
            "document_id": document_id,
            "conversation_id": conversation_id,
        }
        # Future: once backend supports it —
        # payload["response_length"] = response_length

        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=DEFAULT_TIMEOUT * 2)
        return _handle_response(response)
    except requests.exceptions.RequestException as exc:
        return _handle_exception(exc)


def check_backend_health():
    """Lightweight reachability check, used to show a connectivity banner."""
    try:
        requests.get(f"{BASE_URL}/documents", timeout=5)
        return True
    except requests.exceptions.RequestException:
        return False
