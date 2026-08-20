print("========== LOADED BACKEND.PY ==========")
from database.db import init_db
import json
from database.document_store import  update_document_status
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from citation_resolver import attach_quotes_to_sources, iter_resolved_stream
from rag import ask_question
from llm_service import generate_response_stream
from indexer import index_pdf
from fastapi import UploadFile, File
import shutil
import os
from typing import List, Optional
from response_validator import is_valid_response
from database.document_store import create_document
from memory.manager import get_history
from memory.store import (
    save_message,
    delete_conversation,
    create_conversation,
    list_conversations,
    get_conversation,
    rename_conversation,
    delete_last_assistant_message,
)
from database.document_service import (
    list_documents,
    get_document_details,
    remove_document
)
from quote_evidence import resolve_quote_evidence
from config import DATA_DIR
from modes import (
    MODE_SUPER_FOCUSED,
    insufficient_context_payload,
    resolve_document_scope,
)
from agent_foundation import effective_mode

app = FastAPI()

init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Accept-Ranges", "Content-Range", "Content-Length"],
)

class Source(BaseModel):
    document_id: str
    filename: str
    page: Optional[int] = None
    chunk_id: str
    relevance: int
    evidence_id: Optional[str] = None
    snippet: Optional[str] = None
    quote: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[Source]

class ChatRequest(BaseModel):
    question: str
    conversation_id: str
    document_ids: List[str] | None = None
    mode: str = "normal"
    regenerate: bool = False


def _prepare_chat_history(request: ChatRequest) -> list:
    """Load rewrite history. Regenerating replaces the last assistant turn."""
    if request.regenerate:
        delete_last_assistant_message(request.conversation_id)

    history = get_history(request.conversation_id)
    if (
        request.regenerate
        and history
        and history[-1].get("role") == "user"
        and history[-1].get("content") == request.question
    ):
        return history[:-1]
    return history


def _scoped_document_ids(request: ChatRequest) -> tuple[list[str] | None, dict | None]:
    """
    Apply product mode to the existing document_ids retrieval filter.
    Returns (scoped_ids, early_response). early_response is set when Super
    Focused has no selected document — do not retrieve other uploads.
    """
    mode = effective_mode(request.mode)

    scoped = resolve_document_scope(mode, request.document_ids)
    if mode == MODE_SUPER_FOCUSED and not scoped:
        return None, insufficient_context_payload()
    return scoped, None


def _document_pdf_path(filename: str) -> str | None:
    if not filename:
        return None
    data_root = os.path.abspath(DATA_DIR)
    os.makedirs(data_root, exist_ok=True)
    candidate = os.path.abspath(os.path.join(data_root, filename))
    try:
        common = os.path.commonpath([data_root, candidate])
    except ValueError:
        return None
    if common != data_root:
        return None
    if not os.path.isfile(candidate):
        return None
    return candidate

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    history = _prepare_chat_history(request)

    scoped_ids, early = _scoped_document_ids(request)
    if early is not None:
        if not request.regenerate:
            save_message(
                request.conversation_id,
                "user",
                request.question
            )
        answer = early["answer"]
        if is_valid_response(answer):
            save_message(
                request.conversation_id,
                "assistant",
                answer
            )
        return early

    # 2. Ask RAG system
    response = ask_question(
        request.question,
        history,
        scoped_ids,
        mode=effective_mode(request.mode),
    )


    # 3. Save user message (skip on regenerate — it is already stored)
    if not request.regenerate:
        save_message(
            request.conversation_id,
            "user",
            request.question
                )


    # 4. Save assistant response only if valid

    answer = response["answer"]

    if is_valid_response(answer):

        save_message(
            request.conversation_id,
            "assistant",
            answer,
            citations=response.get("sources") or [],
                )


    return response
 
@app.post("/chat/stream")
def chat_stream(request: ChatRequest):


    def generate():

        history = _prepare_chat_history(request)

        scoped_ids, early = _scoped_document_ids(request)
        if early is not None:
            if not request.regenerate:
                save_message(
                    request.conversation_id,
                    "user",
                    request.question,
                )
            answer = early.get("answer") or (
                "No relevant information found in the document."
            )
            if is_valid_response(answer):
                save_message(
                    request.conversation_id,
                    "assistant",
                    answer,
                    citations=[],
                )
            yield f"__CITATIONS__{json.dumps([])}__END_CITATIONS__"
            yield answer
            return


        # Retrieve/rerank once; do not fully generate here (stream generates once).
        response = ask_question(
            request.question,
            history,
            scoped_ids,
            generate=False,
            mode=effective_mode(request.mode),
        )


        # Match /chat: persist user message after successful retrieval prep.
        if not request.regenerate:
            save_message(
                request.conversation_id,
                "user",
                request.question,
            )


        sources = response.get(
            "sources",
            []
        )


        prompt = response.get(
            "prompt"
        )


        # Send citations first
        yield f"__CITATIONS__{json.dumps(sources)}__END_CITATIONS__"


        if not prompt:

            answer = response.get("answer") or (
                "No relevant information found in the document."
            )

            if is_valid_response(answer):

                save_message(
                    request.conversation_id,
                    "assistant",
                    answer,
                    citations=sources,
                )

            yield answer

            return



        answer_parts: list[str] = []
        completed = False

        try:

            for chunk in iter_resolved_stream(
                generate_response_stream(prompt),
                sources,
            ):

                answer_parts.append(chunk)
                yield chunk

            completed = True

        except Exception:

            # Do not save a partial assistant response on stream failure.
            raise

        if completed:

            answer = "".join(answer_parts)

            if is_valid_response(answer):

                save_message(
                    request.conversation_id,
                    "assistant",
                    answer,
                    citations=attach_quotes_to_sources(sources, answer),
                )



    return StreamingResponse(
        generate(),
        media_type="text/plain"
    )

@app.delete("/memory/{conversation_id}")
def delete_memory(conversation_id: str):

    delete_conversation(conversation_id)

    return {
        "message": f"Conversation '{conversation_id}' cleared."
    }


class ConversationCreateRequest(BaseModel):
    title: str | None = None


class ConversationRenameRequest(BaseModel):
    title: str


@app.get("/conversations")
def conversations():
    return list_conversations()


@app.post("/conversations")
def conversation_create(request: ConversationCreateRequest | None = None):
    title = request.title if request else None
    return create_conversation(title)


@app.get("/conversations/{conversation_id}")
def conversation_detail(conversation_id: str):
    record = get_conversation(conversation_id)
    if not record:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return record


@app.patch("/conversations/{conversation_id}")
def conversation_rename(
    conversation_id: str,
    request: ConversationRenameRequest,
):
    record = rename_conversation(conversation_id, request.title)
    if not record:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "conversation_id": record["conversation_id"],
        "title": record["title"],
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
    }


@app.delete("/conversations/{conversation_id}")
def conversation_delete(conversation_id: str):
    delete_conversation(conversation_id)
    return {
        "message": f"Conversation '{conversation_id}' cleared."
    }

@app.post("/upload")
def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):

    print("========== UPLOAD ENDPOINT CALLED ==========")

    os.makedirs(DATA_DIR, exist_ok=True)

    file_path = os.path.join(
        DATA_DIR,
        file.filename
    )

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(
            file.file,
            buffer
        )


    # Create database record immediately
    document_id = create_document(
        file.filename
    )


    # Start indexing in background
    background_tasks.add_task(
        index_pdf,
        file_path,
        document_id
    )


    return {
        "document_id": document_id,
        "status": "uploaded"
    }

@app.get("/documents")
def documents():

    return list_documents()

@app.get("/documents/{document_id}")
def document_details(document_id: str):

    document = get_document_details(
        document_id
    )


    if not document:
        return {
            "error": "Document not found"
        }


    return document


@app.get("/documents/{document_id}/file")
def document_file(document_id: str):
    """Serve the original uploaded PDF for in-app page preview."""

    document = get_document_details(document_id)
    if not document or document.get("error"):
        raise HTTPException(status_code=404, detail="Document not found")

    filename = document.get("filename") or ""
    path = _document_pdf_path(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "private, max-age=60",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/documents/{document_id}/chunks/{chunk_id}/evidence")
def chunk_evidence(document_id: str, chunk_id: str, quote: str | None = None):
    """Return Phase 1 chunk_evidence, optionally narrowed to a verbatim quote."""

    document = get_document_details(document_id)
    if not document or document.get("error"):
        raise HTTPException(status_code=404, detail="Document not found")

    filename = document.get("filename") or ""
    path = _document_pdf_path(filename)
    payload = resolve_quote_evidence(
        document_id=document_id,
        chunk_id=chunk_id,
        quote=quote,
        pdf_path=path,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return payload


@app.delete("/documents/{document_id}")
def delete_document_api(document_id: str):

    deleted = remove_document(
        document_id
    )


    if deleted:
        return {
            "message": "Document deleted successfully"
        }


    return {
        "error": "Document not found"
    }