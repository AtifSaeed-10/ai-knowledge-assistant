from ollama import Client

from config import (
    OLLAMA_HOST,
    LLM_MODEL
)


def generate_ollama_stream(prompt: str):

    client = Client(
        host=OLLAMA_HOST
    )


    stream = client.chat(
        model=LLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        stream=True
    )


    for chunk in stream:

        content = chunk["message"]["content"]

        if content:
            yield content



def generate_ollama_response(prompt: str) -> str:

    client = Client(
        host=OLLAMA_HOST
    )


    response = client.chat(
        model=LLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )


    return response["message"]["content"]