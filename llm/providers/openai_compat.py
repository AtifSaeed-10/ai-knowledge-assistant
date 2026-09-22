"""OpenAI-compatible chat completions (Cerebras, OpenRouter)."""

from __future__ import annotations

from collections.abc import Iterator

import httpx

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


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float,
        extra_headers: dict[str, str] | None = None,
        client: httpx.Client | None = None,
    ):
        self.name = name
        self._api_key = api_key or ""
        self._model = model or ""
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._extra_headers = extra_headers or {}
        self._client = client

    def model_id(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        return bool(self._api_key.strip() and self._model.strip())

    def _require_config(self) -> None:
        if not self.is_configured():
            raise NonRetryableLLMError(
                f"{self.name} is not configured",
                category=CATEGORY_INVALID_CONFIG,
                provider=self.name,
                allow_fallback=True,
            )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self._extra_headers)
        return headers

    def _payload(self, prompt: str, stream: bool) -> dict:
        return {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
        }

    def generate(self, prompt: str) -> str:
        self._require_config()
        url = f"{self._base_url}/chat/completions"
        try:
            if self._client is not None:
                response = self._client.post(
                    url,
                    headers=self._headers(),
                    json=self._payload(prompt, stream=False),
                    timeout=self._timeout,
                )
            else:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(
                        url,
                        headers=self._headers(),
                        json=self._payload(prompt, stream=False),
                    )
            raise_for_status(response, provider=self.name)
            data = parse_json(response.text)
            choices = data.get("choices") or []
            message = (choices[0] if choices else {}).get("message") or {}
            text = message.get("content") or ""
        except Exception as exc:
            raise map_httpx_error(exc, provider=self.name) from None
        if not str(text).strip():
            raise RetryableLLMError(
                f"{self.name} returned an empty response",
                category=CATEGORY_EMPTY,
                provider=self.name,
                retry_same=False,
            )
        return str(text)

    def stream(self, prompt: str) -> Iterator[str]:
        self._require_config()
        url = f"{self._base_url}/chat/completions"
        try:
            client = self._client or httpx.Client(timeout=self._timeout)
            close_client = self._client is None
            try:
                with client.stream(
                    "POST",
                    url,
                    headers=self._headers(),
                    json=self._payload(prompt, stream=True),
                ) as response:
                    raise_for_stream_status(response, provider=self.name)
                    for payload in iter_sse_data_lines(response):
                        data = parse_json(payload)
                        choices = data.get("choices") or []
                        delta = (choices[0] if choices else {}).get("delta") or {}
                        content = delta.get("content")
                        if content:
                            yield str(content)
            finally:
                if close_client:
                    client.close()
        except Exception as exc:
            raise map_httpx_error(exc, provider=self.name) from None
