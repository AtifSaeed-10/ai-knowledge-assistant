"""Compatibility wrapper. New code should use GroqProvider / llm_service."""

from llm.providers.groq import GroqProvider


def generate_groq_response(prompt: str) -> str:
    return GroqProvider().generate(prompt)


def generate_groq_stream(prompt: str):
    yield from GroqProvider().stream(prompt)
