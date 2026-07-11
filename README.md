# AI Knowledge Assistant

A local-first Retrieval-Augmented Generation (RAG) application that allows users to query their own documents using semantic search and Large Language Models.

The system combines document processing, vector databases, FastAPI backend services, and configurable LLM providers with automatic failover between local and cloud inference.

---

# 🚀 Overview

Large Language Models are powerful, but they do not automatically have access to private documents.

This project explores how **Retrieval-Augmented Generation (RAG)** solves this problem by combining:

* Document retrieval
* Vector embeddings
* Semantic search
* Context-based LLM generation

Instead of relying only on model knowledge, answers are generated using information retrieved from user-provided documents.

---

# ✨ Features

## Intelligent Document Question Answering

* Upload PDF documents
* Extract and process document content
* Split documents into meaningful chunks
* Generate vector embeddings
* Store embeddings in ChromaDB
* Retrieve relevant information using semantic search
* Generate grounded answers using LLMs

---

# 🧠 RAG Pipeline

Complete Retrieval-Augmented Generation workflow:

```
PDF Document
      |
      v
Text Extraction
      |
      v
Chunking
      |
      v
Embedding Generation
      |
      v
ChromaDB Vector Storage
      |
      v
Semantic Retrieval
      |
      v
Context Augmentation
      |
      v
LLM Response Generation
```

---

# 🤖 LLM Provider Architecture

The system supports multiple LLM providers.

## Primary Provider

```
Ollama
(Local LLM Inference)
```

## Fallback Provider

```
Groq API
(Cloud LLM Inference)
```

If the primary provider is unavailable, the application automatically switches to the fallback provider.

Example:

```
User Question

        |
        v

LLM Service Router

        |
        |
        +---------- Ollama
        |
        |
        +---------- Groq

        |
        v

Generated Response
```

---

# 🏗️ System Architecture

```
                 User
                  |
                  v
            Streamlit UI
                  |
                  v
             FastAPI API
                  |
                  v
            RAG Pipeline
                  |
        ---------------------
        |                   |
        v                   v
    ChromaDB          LLM Service
    Vector DB              |
                           |
              -------------------------
              |                       |
              v                       v
           Ollama                  Groq API
        (Local Model)          (Cloud Model)
```

---

# 🛠️ Tech Stack

## Backend

* Python
* FastAPI
* Uvicorn

## Frontend

* Streamlit

## AI / Machine Learning

* Retrieval-Augmented Generation (RAG)
* Vector Embeddings
* Semantic Search
* Large Language Models

## Vector Database

* ChromaDB

## Embedding Model

* BAAI/bge-small-en-v1.5

## LLM Providers

* Ollama
* Groq API

## Infrastructure

* Docker
* Environment Variables

---

# 🎯 Design Decisions

## Why RAG?

RAG allows LLMs to answer questions using external knowledge sources without retraining the model.

The system retrieves relevant document sections and provides them as context before generating a response.

---

## Why ChromaDB?

ChromaDB provides persistent vector storage and efficient similarity search for document embeddings.

---

## Why FastAPI?

FastAPI separates the AI pipeline from the user interface and provides a clean API layer similar to production AI systems.

---

## Why Ollama + Groq?

Ollama enables private local inference.

Groq provides fast cloud inference when local resources are unavailable.

The fallback architecture improves reliability.

---

## Why Environment Variables?

Configuration such as:

* API keys
* Models
* Providers
* Database paths

are separated from application code, making the system easier to configure and deploy securely.

---

# 📂 Project Structure

```
ai-knowledge-assistant/

│
├── backend.py              # FastAPI API endpoints
├── streamlit_app.py        # User interface
│
├── rag.py                  # RAG pipeline
├── indexer.py              # Document processing and indexing
│
├── llm_service.py          # LLM routing and fallback logic
├── ollama_service.py       # Ollama integration
├── groq_service.py         # Groq API integration
│
├── config.py               # Application configuration
├── utils.py                # Helper functions
│
├── chroma_db/              # Persistent vector database
├── data/                   # Uploaded documents
│
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

---

# ⚙️ Installation

Clone the repository:

```bash
git clone https://github.com/yourusername/ai-knowledge-assistant.git
```

Move into the project:

```bash
cd ai-knowledge-assistant
```

Create virtual environment:

```bash
python -m venv venv
```

Activate environment:

Windows:

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# 🔐 Environment Variables

Create a `.env` file:

```
LLM_MODEL=qwen2.5:3b

OLLAMA_HOST=http://localhost:11434

PRIMARY_LLM=ollama

FALLBACK_LLM=groq

GROQ_API_KEY=your_api_key_here

CHROMA_DB_PATH=./chroma_db

COLLECTION_NAME=ml_notes

TOP_K=3

SIMILARITY_THRESHOLD=1.3
```

---

# ▶️ Running Locally

## Start Ollama

Install Ollama and make sure it is running:

```bash
ollama serve
```

Check available models:

```bash
ollama list
```

---

## Start FastAPI Backend

```bash
uvicorn backend:app --reload
```

Backend:

```
http://127.0.0.1:8000
```

API documentation:

```
http://127.0.0.1:8000/docs
```

---

## Start Streamlit Frontend

Open another terminal:

```bash
streamlit run streamlit_app.py
```

Frontend:

```
http://localhost:8501
```

---

# 🐳 Running With Docker

Build image:

```bash
docker build -t ai-knowledge-assistant .
```

Run container:

```bash
docker run \
-p 8000:8000 \
-e OLLAMA_HOST=http://host.docker.internal:11434 \
ai-knowledge-assistant
```

The `OLLAMA_HOST` variable allows the container to communicate with Ollama running on the host machine.

---

# 🔌 API Endpoints

## Health Check

```
GET /health
```

---

## Upload Document

```
POST /upload
```

Uploads and indexes PDF documents.

---

## Ask Question

```
POST /chat
```

Example:

```json
{
  "question": "What is supervised learning?"
}
```

---

# 🔍 How It Works

1. User uploads a PDF.
2. Text is extracted from the document.
3. Text is divided into smaller chunks.
4. Chunks are converted into embeddings.
5. Embeddings are stored in ChromaDB.
6. User asks a question.
7. Relevant chunks are retrieved.
8. Retrieved context is sent to the LLM.
9. The LLM generates the final answer.

---

# 📌 Engineering Concepts Demonstrated

This project demonstrates practical experience with:

* RAG system design
* Vector databases
* Embedding models
* Semantic retrieval
* FastAPI backend development
* LLM provider abstraction
* Failure handling
* Docker containerization
* AI application architecture

---

# 📊 Project Status

Version: 1.0

Completed:

✅ Document ingestion pipeline
✅ Vector database integration
✅ Semantic retrieval system
✅ FastAPI backend
✅ Streamlit interface
✅ Docker containerization
✅ Multi-provider LLM routing
✅ Ollama → Groq automatic fallback

Planned improvements:

* Streaming responses
* Authentication
* Multiple document collections
* Conversation memory
* LangSmith monitoring
* Cloud deployment
* Agent workflows

---

# 📸 Screenshots

(Add screenshots after deployment)

Example:

```
screenshots/
├── chat-interface.png
└── api-docs.png
```

---

# 👨‍💻 Author

Atif Saeed

Computer Science Student focused on AI Engineering and LLM applications.

Building practical AI systems with modern machine learning and generative AI technologies.
