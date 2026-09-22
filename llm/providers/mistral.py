from __future__ import annotations

from collections.abc import Iterator

import httpx

from config import LLM_REQUEST_TIMEOUT, MISTRAL_API_KEY, MISTRAL_MODEL
from llm.providers.openai_compat import OpenAICompatProvider


class MistralProvider(OpenAICompatProvider):
    name = "mistral"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ):
        super().__init__(
            name="mistral",
            api_key=(api_key if api_key is not None else MISTRAL_API_KEY) or "",
            model=(model if model is not None else MISTRAL_MODEL) or "",
            base_url="https://api.mistral.ai/v1",
            timeout=LLM_REQUEST_TIMEOUT if timeout is None else timeout,
            client=client,
        )

    def generate(self, prompt: str) -> str:
        return super().generate(prompt)

    def stream(self, prompt: str) -> Iterator[str]:
        yield from super().stream(prompt)
