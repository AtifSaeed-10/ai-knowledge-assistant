from groq import Groq

from config import GROQ_API_KEY


def generate_groq_stream(prompt: str):

    client = Groq(
        api_key=GROQ_API_KEY
    )


    stream = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        stream=True
    )


    for chunk in stream:

        content = chunk.choices[0].delta.content

        if content:
            yield content



def generate_groq_response(prompt: str) -> str:

    client = Groq(
        api_key=GROQ_API_KEY
    )


    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )


    return response.choices[0].message.content