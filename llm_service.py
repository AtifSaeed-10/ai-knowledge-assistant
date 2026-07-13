from config import (
    PRIMARY_LLM,
    FALLBACK_LLM,
)

from ollama_service import generate_ollama_response
from groq_service import generate_groq_response


providers = {
    "ollama": generate_ollama_response,
    "groq": generate_groq_response,
}


def generate_response(prompt: str) -> str:

    try:
        print("\n" + "=" * 50)
        print(f"Using provider: {PRIMARY_LLM}")
        print("=" * 50)

        response = providers[PRIMARY_LLM](prompt)

        print("Response generated successfully.")

        return response

    except Exception as e:

        print("\n" + "=" * 50)
        print("PRIMARY PROVIDER FAILED")
        print("=" * 50)
        print(e)

        print("\nTrying fallback provider...")
        print(f"Fallback Provider: {FALLBACK_LLM}")

        response = providers[FALLBACK_LLM](prompt)

        print("Fallback response generated successfully.")

        return response