"""Stable generation facade. RAG code should keep calling these two functions."""

from llm.errors import GENERATION_UNAVAILABLE
from llm.router import get_router


def generate_response(prompt: str) -> str:
    return get_router().generate(prompt)


def generate_response_stream(prompt: str):
    yield from get_router().stream(prompt)


__all__ = [
    "GENERATION_UNAVAILABLE",
    "generate_response",
    "generate_response_stream",
]
