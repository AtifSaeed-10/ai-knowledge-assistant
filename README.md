# 🤖 AI Knowledge Assistant

A production-style **Retrieval-Augmented Generation (RAG)** application that allows users to upload PDF documents and ask questions about their content using semantic search and Large Language Models.

The system combines document processing, vector databases, FastAPI backend services, Streamlit frontend, Docker containerization, and configurable LLM providers with automatic failover between local and cloud inference.

---

# 🚀 Live Demo

Try the application here:

🔗 **Streamlit App:**
https://ai-knowledge-assistant-6969.streamlit.app/

Backend API:

https://ai-knowledge-assistant-voy8.onrender.com

---

# 📌 Overview

Large Language Models are powerful, but they do not automatically have access to private or user-specific documents.

This project demonstrates how **Retrieval-Augmented Generation (RAG)** solves this limitation by combining:

* Document ingestion
* Text chunking
* Vector embeddings
* Semantic retrieval
* Context augmentation
* LLM-based answer generation

Instead of relying only on the model's existing knowledge, responses are generated using information retrieved directly from user-provided documents.

---

# ✨ Features

## 📄 Intelligent Document Question Answering

Users can:

* Upload PDF documents
* Automatically extract document text
* Split documents into meaningful chunks
* Generate semantic embeddings
* Store embeddings in ChromaDB
* Retrieve relevant document sections
* Ask questions using natural language
* Receive context-grounded answers

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
Context Injection
      |
      v
LLM Generation
      |
      v
Final Answer
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
              FastAPI Backend
                     |
                     v
              RAG Pipeline
                     |
        --------------------------
        |                        |
        v                        v
    ChromaDB              LLM Service
   Vector Database              |
                                |
                 ---------------------------
                 |                         |
                 v                         v
              Ollama                   Groq API
          Local Inference          Cloud Inference
```

---

# 🤖 LLM Provider Architecture

The application supports multiple LLM providers through an abstraction layer.

## Local Development

Primary:

```
Ollama
(Local LLM inference)
```

Fallback:

```
Groq API
(Cloud inference)
```

## Cloud Deployment

The deployed version uses:

```
Groq API
```

because cloud environments do not run the local Ollama server.

The provider architecture allows switching models/providers without changing the RAG pipeline.

Example:

```
User Question

        |
        v

   LLM Service Router

        |
        |
        +------------ Ollama
        |
        |
        +------------ Groq API

        |
        v

 Generated Response
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
* Semantic Search
* Vector Embeddings
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
* Render
* Streamlit Cloud
* Environment Variables

---

# 🎯 Design Decisions

## Why RAG?

RAG allows Large Language Models to answer questions using external knowledge sources without retraining the model.

The system retrieves relevant document chunks and provides them as context before generating a response.

---

## Why ChromaDB?

ChromaDB provides persistent vector storage and efficient similarity search for embedding-based retrieval.

---

## Why FastAPI?

FastAPI separates the AI pipeline from the frontend and creates a clean API layer similar to production AI applications.

---

## Why Ollama + Groq?

Ollama enables private local inference during development.

Groq provides fast cloud inference for deployment environments.

The fallback architecture improves reliability.

---

## Why Environment Variables?

Sensitive and configurable values are separated from application code:

* API keys
* Model selection
* LLM providers
* Database paths
* Runtime configuration

This improves security and deployment flexibility.

---

# 📂 Project Structure

```
ai-knowledge-assistant/

│
├── backend.py              # FastAPI API endpoints
├── streamlit_app.py        # Streamlit user interface
│
├── rag.py                  # Retrieval-Augmented Generation pipeline
├── indexer.py              # PDF processing and indexing
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
├── render.yaml
├── .env.example
└── README.md
```

---

# ⚙️ Local Installation

Clone repository:

```bash
git clone https://github.com/yourusername/ai-knowledge-assistant.git
```

Move into project:

```bash
cd ai-knowledge-assistant
```

Create virtual environment:

```bash
python -m venv venv
```

Activate:

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

```bash
ollama serve
```

Check models:

```bash
ollama list
```

---

## Start Backend

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

## Start Frontend

Open another terminal:

```bash
streamlit run streamlit_app.py
```

Frontend:

```
http://localhost:8501
```

---

# 🐳 Docker Support

Build image:

```bash
docker build -t ai-knowledge-assistant .
```

Run:

```bash
docker run \
-p 8000:8000 \
-e OLLAMA_HOST=http://host.docker.internal:11434 \
ai-knowledge-assistant
```

Docker allows the backend to run inside a container while communicating with external LLM services.

---

# 🔌 API Endpoints

## Health Check

```
GET /health
```

---

## Upload PDF

```
POST /upload
```

Uploads and indexes documents into the vector database.

---

## Ask Question

```
POST /chat
```

Example:

```json
{
  "question": "Explain supervised learning"
}
```

---

# 🔍 How It Works

1. User uploads a PDF.
2. Text is extracted.
3. Content is split into chunks.
4. Chunks are converted into embeddings.
5. Embeddings are stored in ChromaDB.
6. User submits a question.
7. Relevant chunks are retrieved.
8. Retrieved context is sent to the LLM.
9. The model generates a grounded response.

---

# 📊 Engineering Concepts Demonstrated

This project demonstrates practical AI engineering skills:

* RAG system design
* Vector database implementation
* Embedding-based retrieval
* Semantic search
* FastAPI backend development
* Streamlit application development
* LLM provider abstraction
* Environment-based configuration
* Error handling and fallback systems
* Docker containerization
* Cloud deployment

---

# ✅ Project Status

## Version: 1.0.0

Completed:

✅ PDF ingestion pipeline
✅ Text chunking system
✅ Embedding generation
✅ ChromaDB vector storage
✅ Semantic retrieval
✅ FastAPI backend
✅ Streamlit frontend
✅ Docker containerization
✅ Multi-provider LLM architecture
✅ Ollama → Groq fallback
✅ Render backend deployment
✅ Streamlit Cloud deployment

---


# 👨‍💻 Author

**Atif Saeed**

Computer Science student focused on AI Engineering and Large Language Model applications.

Building practical AI systems using modern machine learning, retrieval systems, and generative AI technologies.
