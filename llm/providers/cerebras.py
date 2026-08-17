from __future__ import annotations

from collections.abc import Iterator

import httpx

from config import CEREBRAS_API_KEY, CEREBRAS_MODEL, LLM_REQUEST_TIMEOUT
from llm.providers.openai_compat import OpenAICompatProvider


class CerebrasProvider(OpenAICompatProvider):
    name = "cerebras"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ):
        super().__init__(
            name="cerebras",
            api_key=(api_key if api_key is not None else CEREBRAS_API_KEY) or "",
            model=(model if model is not None else CEREBRAS_MODEL) or "",
            base_url="https://api.cerebras.ai/v1",
            timeout=LLM_REQUEST_TIMEOUT if timeout is None else timeout,
            client=client,
        )

    def generate(self, prompt: str) -> str:
        return super().generate(prompt)

    def stream(self, prompt: str) -> Iterator[str]:
        yield from super().stream(prompt)
