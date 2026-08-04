print("========== LOADED BACKEND.PY ==========")
from database.db import init_db
import json
from database.document_store import  update_document_status
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rag import ask_question
from llm_service import generate_response_stream
from indexer import index_pdf
from fastapi import UploadFile, File
import shutil
import os
from typing import List
from response_validator import is_valid_response
from database.document_store import create_document
from memory.manager import get_history
from memory.store import (
    save_message,
    delete_conversation
)
from database.document_service import (
    list_documents,
    get_document_details,
    remove_document
)

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
)

class Source(BaseModel):
    document_id: str
    filename: str
    page: int
    chunk_id: str
    relevance: int


class ChatResponse(BaseModel):
    answer: str
    sources: List[Source]

class ChatRequest(BaseModel):
    question: str
    conversation_id: str
    document_ids: List[str] | None = None

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    # 1. Get previous conversation
    history = get_history(
        request.conversation_id
    )


    # 2. Ask RAG system
    response = ask_question(
        request.question,
        history,
        request.document_ids
    )


    # 3. Save user message
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
            answer
                )


    return response
 
@app.post("/chat/stream")
def chat_stream(request: ChatRequest):


    def generate():

        history = get_history(
            request.conversation_id
        )


        response = ask_question(
            request.question,
            history,
            request.document_ids
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

            yield response["answer"]

            return



        for chunk in generate_response_stream(prompt):

            yield chunk



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

@app.post("/upload")
def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):

    print("========== UPLOAD ENDPOINT CALLED ==========")

    os.makedirs("data", exist_ok=True)

    file_path = os.path.join(
        "data",
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