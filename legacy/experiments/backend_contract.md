# DocuSage Frontend Backend Contract

Base URL:

Development:
http://localhost:8000


## 1. Backend Health

### GET /health

Purpose:
Check whether backend is available.

Response:

{
  "status": "ok"
}


Frontend usage:

- Green indicator when available
- Red indicator when backend is offline


--------------------------------------------------


# Documents


## 2. Upload PDF

### POST /upload

Purpose:

Upload a PDF and index it into the knowledge base.


Request:

Content-Type:
multipart/form-data


Body:

file:
PDF document


Example:

file = Machine Learning.pdf


Response:

{
  "message": "PDF indexed successfully!"
}


Frontend behavior:

During upload show:

1. Uploading file
2. Extracting text
3. Splitting chunks
4. Creating embeddings
5. Building search index
6. Ready


Future improvement:

Backend should return:

{
 "document_id":"",
 "filename":"",
 "chunks":381
}


--------------------------------------------------


## 3. List Documents


### GET /documents


Purpose:

Get all uploaded PDFs.


Response:

Example:

[
 {
  "document_id":"abc123",
  "filename":"Machine Learning.pdf",
  "upload_time":"2026-07-30",
  "total_pages":120,
  "total_chunks":381
 }
]


Frontend usage:

Sidebar Documents section.


Display:

- Filename
- Pages
- Number of chunks
- Delete option


--------------------------------------------------


## 4. Get Document Details


### GET /documents/{document_id}


Purpose:

Get information about a specific PDF.


Response:


{
 "document_id":"",
 "filename":"",
 "upload_time":"",
 "total_pages":120,
 "total_chunks":381
}


Frontend usage:

Document details panel.


--------------------------------------------------


## 5. Delete Document


### DELETE /documents/{document_id}


Purpose:

Remove PDF from knowledge base.


Response:


Success:

{
 "message":"Document deleted successfully"
}


Failure:

{
 "error":"Document not found"
}


Frontend behavior:

Show confirmation dialog:

"Are you sure you want to delete this document?"


--------------------------------------------------


# Chat System


## 6. Ask Question


### POST /chat


Purpose:

Ask questions from uploaded documents.


Request:


{
 "question":"What is supervised learning?",
 "conversation_id":"abc123",
 "document_id":"xyz123"
}


Response:


{
 "answer":"Supervised learning is...",
 
 "sources":[
  {
   "document_id":"",
   "filename":"",
   "page":5,
   "chunk_id":23,
   "distance":0.34
  }
 ]
}


Frontend usage:


Chat interface.

Display:

User message

↓

Assistant response

↓

Sources card


--------------------------------------------------


# Conversation Memory


## 7. Clear Conversation


### DELETE /memory/{conversation_id}


Purpose:

Delete current conversation history.


Response:


{
 "message":"Conversation cleared."
}


Frontend usage:

Clear chat button.


--------------------------------------------------


# Frontend Required States


## Backend Status

Available:

Green indicator


Unavailable:

Red indicator


## Upload States


Uploading

Extracting text

Splitting chunks

Creating embeddings

Building index

Ready


## Error States


Backend unavailable

Upload failed

Invalid PDF

No relevant information found

