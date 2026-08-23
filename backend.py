print("========== LOADED BACKEND.PY ==========")
from database.db import init_db
import json
from database.document_store import  update_document_status
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from citation_resolver import iter_resolved_stream
from claim_validator import finalize_answer_citations
from evidence_state import visible_sources
from evidence_trace import attach_trace_dict_to_sources
from rag import ask_question
from llm_service import generate_response, generate_response_stream
from grounding_verifier import verify_and_repair_refusal
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
from quote_evidence import resolve_claim_evidence, resolve_quote_evidence
from database.evidence_store import document_evidence_summary
from document_paths import document_pdf_path, stored_pdf_path
from index_hygiene import reconcile_index, resolve_retrieval_scope
from config import DATA_DIR
from modes import (
    insufficient_context_payload,
)
from agent_foundation import effective_mode

app = FastAPI()

init_db()
try:
    reconcile_index()
except Exception:
    print("index reconcile failed; continuing startup")

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
    quotes: Optional[List[str]] = None
    quote_mapping_status: Optional[str] = None
    quote_highlight_available: Optional[bool] = None
    quote_regions: Optional[List[dict]] = None
    evidence_state: Optional[str] = None
    citation_eligible: Optional[bool] = None
    ui_status: Optional[str] = None
    content_type: Optional[str] = None


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
    Apply product mode and live-corpus isolation to retrieval.
    Super Focused with no ready selected document aborts without search.
    Normal mode receives an explicit ready-id list (empty = search nothing).
    """
    mode = effective_mode(request.mode)
    scoped, abort = resolve_retrieval_scope(mode, request.document_ids)
    if abort:
        return None, insufficient_context_payload()
    return scoped, None


def _document_pdf_path(filename: str) -> str | None:
    from document_paths import pdf_path_for_filename

    return pdf_path_for_filename(filename)

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
            citations=visible_sources(response.get("sources") or [], answer),
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

            streamed_answer = "".join(answer_parts)
            answer, grounding = verify_and_repair_refusal(
                streamed_answer,
                question=request.question,
                prompt=prompt,
                sources=sources,
                recall_candidates=response.get("recall_candidates"),
                analysis=response.get("analysis"),
                generate_fn=generate_response,
            )
            repaired = grounding.get("action") in {"retry", "extractive"}
            finalize_result = finalize_answer_citations(
                answer,
                sources,
                recall_candidates=response.get("recall_candidates"),
                emit_trace=True,
                conversation_id=request.conversation_id,
                question=request.question,
            )
            trace_payload: dict | None = None
            if len(finalize_result) == 3:
                answer, enriched_sources, trace_payload = finalize_result
            else:
                answer, enriched_sources = finalize_result
            final_sources = visible_sources(
                enriched_sources,
                answer,
                recall_candidates=response.get("recall_candidates"),
            )
            if trace_payload:
                final_sources = attach_trace_dict_to_sources(final_sources, trace_payload)

            if is_valid_response(answer):

                save_message(
                    request.conversation_id,
                    "assistant",
                    answer,
                    citations=final_sources,
                )

            # A repaired refusal invalidates the tokens already on screen.
            # Send the saved answer so the client can replace them.
            if repaired and answer != streamed_answer:
                yield (
                    f"__ANSWER_FINAL__{json.dumps(answer)}__END_ANSWER_FINAL__"
                )

            yield f"__CITATIONS_FINAL__{json.dumps(final_sources)}__END_CITATIONS__"



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

    original_name = os.path.basename(file.filename or "upload.pdf")
    document_id = create_document(original_name)
    file_path = stored_pdf_path(document_id, must_exist=False)
    if file_path is None:
        raise HTTPException(status_code=400, detail="Could not store uploaded file.")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(
            file.file,
            buffer
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
    path = document_pdf_path(document_id)
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
def chunk_evidence(document_id: str, chunk_id: str, quote: str | None = None, claim: str | None = None):
    """Return chunk evidence, localized to a quote and/or paraphrased claim."""

    document = get_document_details(document_id)
    if not document or document.get("error"):
        raise HTTPException(status_code=404, detail="Document not found")

    path = document_pdf_path(document_id)
    if claim and str(claim).strip():
        payload = resolve_claim_evidence(
            document_id=document_id,
            chunk_id=chunk_id,
            claim_text=str(claim).strip(),
            quote=quote,
            pdf_path=path,
        )
    else:
        payload = resolve_quote_evidence(
            document_id=document_id,
            chunk_id=chunk_id,
            quote=quote,
            pdf_path=path,
        )
    if payload is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return payload


@app.get("/documents/{document_id}/evidence-summary")
def document_evidence_summary_api(document_id: str):
    """Highlight availability summary for indexed chunk evidence."""
    document = get_document_details(document_id)
    if not document or document.get("error"):
        raise HTTPException(status_code=404, detail="Document not found")
    return document_evidence_summary(document_id)


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