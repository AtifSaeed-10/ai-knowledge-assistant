from llm.providers.cerebras import CerebrasProvider
from llm.providers.gemini import GeminiProvider
from llm.providers.groq import GroqProvider
from llm.providers.mistral import MistralProvider
from llm.providers.ollama import OllamaProvider
from llm.providers.openrouter import OpenRouterProvider

PROVIDER_CLASSES = {
    "groq": GroqProvider,
    "gemini": GeminiProvider,
    "cerebras": CerebrasProvider,
    "openrouter": OpenRouterProvider,
    "mistral": MistralProvider,
    "ollama": OllamaProvider,
}

__all__ = [
    "CerebrasProvider",
    "GeminiProvider",
    "GroqProvider",
    "MistralProvider",
    "OllamaProvider",
    "OpenRouterProvider",
    "PROVIDER_CLASSES",
]
