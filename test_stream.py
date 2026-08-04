import requests


url = "http://127.0.0.1:8000/chat/stream"


payload = {
    "question": "What is machine learning?",
    "conversation_id": "test-stream-1",
    "document_ids": []
}


response = requests.post(
    url,
    json=payload,
    stream=True
)


print("Status:", response.status_code)

print("\nStreaming response:\n")


for chunk in response.iter_content(
    chunk_size=None
):

    if chunk:

        print(
            chunk.decode("utf-8"),
            end="",
            flush=True
        )