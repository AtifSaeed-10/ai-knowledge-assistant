"""Groq chat completions via the official groq SDK."""

from __future__ import annotations

from collections.abc import Iterator

from config import GROQ_API_KEY, GROQ_MODEL, LLM_REQUEST_TIMEOUT
from llm.base import LLMProvider
from llm.errors import (
    CATEGORY_AUTH,
    CATEGORY_CONNECTION,
    CATEGORY_EMPTY,
    CATEGORY_INVALID_CONFIG,
    CATEGORY_MALFORMED,
    CATEGORY_MODEL_UNAVAILABLE,
    CATEGORY_PROVIDER_UNAVAILABLE,
    CATEGORY_QUOTA,
    CATEGORY_RATE_LIMIT,
    CATEGORY_TIMEOUT,
    LLMError,
    NonRetryableLLMError,
    RetryableLLMError,
)
from llm.sanitize import safe_error_message
from app_platform.ops.groq_limits import store_groq_call, usage_tokens


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        self._api_key = (api_key if api_key is not None else GROQ_API_KEY) or ""
        self._model = (model if model is not None else GROQ_MODEL) or ""
        self._timeout = LLM_REQUEST_TIMEOUT if timeout is None else timeout

    def model_id(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        return bool(self._api_key.strip() and self._model.strip())

    def _client(self):
        if not self.is_configured():
            raise NonRetryableLLMError(
                "groq is not configured",
                category=CATEGORY_INVALID_CONFIG,
                provider=self.name,
                allow_fallback=True,
            )
        from groq import Groq

        return Groq(api_key=self._api_key, timeout=self._timeout)

    def _map_exception(self, exc: BaseException) -> LLMError:
        if isinstance(exc, LLMError):
            return exc
        status = getattr(exc, "status_code", None)
        name = type(exc).__name__.lower()
        if "timeout" in name:
            return RetryableLLMError(
                "groq timed out",
                category=CATEGORY_TIMEOUT,
                provider=self.name,
            )
        if "connection" in name:
            return RetryableLLMError(
                "groq connection failed",
                category=CATEGORY_CONNECTION,
                provider=self.name,
            )
        if "ratelimit" in name or status == 429:
            message = safe_error_message(exc).lower()
            quota = "quota" in message
            return RetryableLLMError(
                "groq quota exhausted" if quota else "groq rate limited",
                category=CATEGORY_QUOTA if quota else CATEGORY_RATE_LIMIT,
                provider=self.name,
                status_code=429,
            )
        if "authentication" in name or status in {401, 403}:
            return LLMError(
                "groq authentication failed",
                category=CATEGORY_AUTH,
                provider=self.name,
                retry_same=False,
                allow_fallback=True,
                status_code=status,
            )
        if "notfound" in name or status == 404:
            return LLMError(
                "groq model unavailable",
                category=CATEGORY_MODEL_UNAVAILABLE,
                provider=self.name,
                retry_same=False,
                allow_fallback=True,
                status_code=404,
            )
        if "badrequest" in name or status in {400, 422}:
            return NonRetryableLLMError(
                "groq rejected the request",
                category=CATEGORY_MALFORMED,
                provider=self.name,
                status_code=status,
            )
        if status is not None and int(status) >= 500:
            return RetryableLLMError(
                "groq unavailable",
                category=CATEGORY_PROVIDER_UNAVAILABLE,
                provider=self.name,
                status_code=int(status),
            )
        return RetryableLLMError(
            f"groq request failed: {safe_error_message(exc)}",
            category=CATEGORY_PROVIDER_UNAVAILABLE,
            provider=self.name,
            retry_same=False,
        )

    def _create(self, prompt: str, *, stream: bool):
        completions = self._client().chat.completions
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if stream:
            payload["stream"] = True
        raw_api = getattr(completions, "with_raw_response", None)
        if raw_api is not None:
            raw = raw_api.create(**payload)
            headers = getattr(raw, "headers", None)
            body = raw.parse() if hasattr(raw, "parse") else raw
            return body, headers
        return completions.create(**payload), None

    def generate(self, prompt: str) -> str:
        try:
            response, headers = self._create(prompt, stream=False)
        except Exception as exc:
            mapped = self._map_exception(exc)
            store_groq_call(None, 0, str(mapped))
            raise mapped from None
        store_groq_call(headers, usage_tokens(response))
        text = ""
        try:
            text = response.choices[0].message.content or ""
        except Exception:
            text = ""
        if not str(text).strip():
            raise RetryableLLMError(
                "groq returned an empty response",
                category=CATEGORY_EMPTY,
                provider=self.name,
                retry_same=False,
            )
        return str(text)

    def stream(self, prompt: str) -> Iterator[str]:
        try:
            stream, headers = self._create(prompt, stream=True)
            store_groq_call(headers, 0)
            for chunk in stream:
                try:
                    content = chunk.choices[0].delta.content
                except Exception:
                    content = None
                if content:
                    yield content
        except LLMError as exc:
            store_groq_call(None, 0, str(exc))
            raise
        except Exception as exc:
            mapped = self._map_exception(exc)
            store_groq_call(None, 0, str(mapped))
            raise mapped from None
