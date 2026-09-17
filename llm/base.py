from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass
class AttemptRecord:
    provider: str
    model: str
    latency_ms: int
    attempt: int
    success: bool
    error_category: str | None = None
    extra: dict = field(default_factory=dict)


class LLMProvider(ABC):
    """One generation backend. HTTP/SDK details stay inside subclasses."""

    name: str = ""

    def model_id(self) -> str:
        return ""

    def is_configured(self) -> bool:
        return True

    @abstractmethod
    def generate(self, prompt: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def stream(self, prompt: str) -> Iterator[str]:
        raise NotImplementedError
