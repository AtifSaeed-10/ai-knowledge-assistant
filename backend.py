print("========== LOADED BACKEND.PY ==========")
from fastapi import FastAPI
from pydantic import BaseModel
from rag import ask_question
from indexer import index_pdf
from fastapi import UploadFile, File
import shutil
import os

app = FastAPI()


class ChatRequest(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    answer = ask_question(request.question)
    return {"answer": answer}

@app.post("/upload")

def upload_pdf(file: UploadFile = File(...)):

    os.makedirs("data", exist_ok=True)

    file_path = os.path.join("data", file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    index_pdf(file_path)

    return {
        "message": "PDF indexed successfully!"
    }
    print("\n========== REGISTERED ROUTES ==========")
for route in app.routes:
    print(route.path, route.methods)