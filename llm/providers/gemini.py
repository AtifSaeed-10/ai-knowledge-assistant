"""Google Gemini via the official generateContent REST API."""

from __future__ import annotations

from collections.abc import Iterator

import httpx

from config import GEMINI_API_KEY, GEMINI_MODEL, LLM_REQUEST_TIMEOUT
from llm.base import LLMProvider
from llm.errors import (
    CATEGORY_EMPTY,
    CATEGORY_INVALID_CONFIG,
    NonRetryableLLMError,
    RetryableLLMError,
)
from llm.http_util import (
    iter_sse_data_lines,
    map_httpx_error,
    parse_json,
    raise_for_status,
    raise_for_stream_status,
)


class GeminiProvider(LLMProvider):
    name = "gemini"
    _BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ):
        self._api_key = (api_key if api_key is not None else GEMINI_API_KEY) or ""
        self._model = (model if model is not None else GEMINI_MODEL) or ""
        self._timeout = LLM_REQUEST_TIMEOUT if timeout is None else timeout
        self._client = client

    def model_id(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        return bool(self._api_key.strip() and self._model.strip())

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

    def _payload(self, prompt: str) -> dict:
        return {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ]
        }

    def _require_config(self) -> None:
        if not self.is_configured():
            raise NonRetryableLLMError(
                "gemini is not configured",
                category=CATEGORY_INVALID_CONFIG,
                provider=self.name,
                allow_fallback=True,
            )

    def _extract_text(self, data: dict) -> str:
        parts: list[str] = []
        for candidate in data.get("candidates") or []:
            content = (candidate or {}).get("content") or {}
            for part in content.get("parts") or []:
                text = (part or {}).get("text")
                if text:
                    parts.append(str(text))
        return "".join(parts)

    def generate(self, prompt: str) -> str:
        self._require_config()
        url = f"{self._BASE}/models/{self._model}:generateContent"
        try:
            if self._client is not None:
                response = self._client.post(
                    url,
                    headers=self._headers(),
                    json=self._payload(prompt),
                    timeout=self._timeout,
                )
            else:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(
                        url,
                        headers=self._headers(),
                        json=self._payload(prompt),
                    )
            raise_for_status(response, provider=self.name)
            text = self._extract_text(parse_json(response.text))
        except Exception as exc:
            raise map_httpx_error(exc, provider=self.name) from None
        if not text.strip():
            raise RetryableLLMError(
                "gemini returned an empty response",
                category=CATEGORY_EMPTY,
                provider=self.name,
                retry_same=False,
            )
        return text

    def stream(self, prompt: str) -> Iterator[str]:
        self._require_config()
        url = f"{self._BASE}/models/{self._model}:streamGenerateContent"
        try:
            client = self._client or httpx.Client(timeout=self._timeout)
            close_client = self._client is None
            try:
                with client.stream(
                    "POST",
                    url,
                    headers=self._headers(),
                    json=self._payload(prompt),
                    params={"alt": "sse"},
                ) as response:
                    raise_for_stream_status(response, provider=self.name)
                    for payload in iter_sse_data_lines(response):
                        text = self._extract_text(parse_json(payload))
                        if text:
                            yield text
            finally:
                if close_client:
                    client.close()
        except Exception as exc:
            raise map_httpx_error(exc, provider=self.name) from None
