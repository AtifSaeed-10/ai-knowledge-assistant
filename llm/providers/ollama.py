"""Optional Ollama provider for backward compatibility."""

from __future__ import annotations

from collections.abc import Iterator

from config import LLM_MODEL, LLM_REQUEST_TIMEOUT, OLLAMA_HOST
from llm.base import LLMProvider
from llm.errors import (
    CATEGORY_CONNECTION,
    CATEGORY_EMPTY,
    CATEGORY_INVALID_CONFIG,
    CATEGORY_PROVIDER_UNAVAILABLE,
    CATEGORY_TIMEOUT,
    LLMError,
    NonRetryableLLMError,
    RetryableLLMError,
)
from llm.sanitize import safe_error_message


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        self._host = host if host is not None else OLLAMA_HOST
        self._model = (model if model is not None else LLM_MODEL) or ""
        self._timeout = LLM_REQUEST_TIMEOUT if timeout is None else timeout

    def model_id(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        return bool(self._host and self._model.strip())

    def _client(self):
        if not self.is_configured():
            raise NonRetryableLLMError(
                "ollama is not configured",
                category=CATEGORY_INVALID_CONFIG,
                provider=self.name,
                allow_fallback=True,
            )
        from ollama import Client

        try:
            return Client(host=self._host, timeout=self._timeout)
        except TypeError:
            return Client(host=self._host)

    def _map_exception(self, exc: BaseException) -> LLMError:
        if isinstance(exc, LLMError):
            return exc
        name = type(exc).__name__.lower()
        message = safe_error_message(exc).lower()
        if "timeout" in name or "timed out" in message:
            return RetryableLLMError(
                "ollama timed out",
                category=CATEGORY_TIMEOUT,
                provider=self.name,
            )
        if "connection" in name or "refused" in message:
            return RetryableLLMError(
                "ollama connection failed",
                category=CATEGORY_CONNECTION,
                provider=self.name,
            )
        return RetryableLLMError(
            f"ollama request failed: {safe_error_message(exc)}",
            category=CATEGORY_PROVIDER_UNAVAILABLE,
            provider=self.name,
            retry_same=False,
        )

    def generate(self, prompt: str) -> str:
        try:
            response = self._client().chat(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise self._map_exception(exc) from None
        text = ""
        if isinstance(response, dict):
            text = (response.get("message") or {}).get("content") or ""
        else:
            text = getattr(getattr(response, "message", None), "content", "") or ""
        if not str(text).strip():
            raise RetryableLLMError(
                "ollama returned an empty response",
                category=CATEGORY_EMPTY,
                provider=self.name,
                retry_same=False,
            )
        return str(text)

    def stream(self, prompt: str) -> Iterator[str]:
        try:
            stream = self._client().chat(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            for chunk in stream:
                if isinstance(chunk, dict):
                    content = (chunk.get("message") or {}).get("content")
                else:
                    content = getattr(getattr(chunk, "message", None), "content", None)
                if content:
                    yield str(content)
        except LLMError:
            raise
        except Exception as exc:
            raise self._map_exception(exc) from None
