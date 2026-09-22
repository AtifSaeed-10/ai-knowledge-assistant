"""Provider router. Same prompt is sent to each fallback; retrieval is never rerun."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator

from config import (
    LLM_FALLBACK_PROVIDERS,
    LLM_MAX_RETRIES_PER_PROVIDER,
    LLM_PRIMARY_PROVIDER,
)
from llm.base import AttemptRecord, LLMProvider
from llm.errors import (
    CATEGORY_INVALID_CONFIG,
    CATEGORY_STREAM_INTERRUPTED,
    GENERATION_UNAVAILABLE,
    LLMError,
    StreamInterruptedError,
)
from llm.providers import PROVIDER_CLASSES
from llm.sanitize import redact_secrets, safe_error_message

logger = logging.getLogger("docusage.llm")

_router: LLMRouter | None = None


def _log(message: str) -> None:
    text = redact_secrets(message)
    logger.info(text)
    print(text)


class LLMRouter:
    def __init__(
        self,
        providers: dict[str, LLMProvider],
        primary: str,
        fallbacks: list[str],
        max_retries_per_provider: int = 1,
    ):
        self.providers = providers
        self.primary = primary
        self.fallbacks = [name for name in fallbacks if name and name != primary]
        self.max_retries_per_provider = max(0, int(max_retries_per_provider))
        self.attempts: list[AttemptRecord] = []
        self._last_failure: LLMError | None = None

    @classmethod
    def from_config(cls) -> LLMRouter:
        providers = {name: factory() for name, factory in PROVIDER_CLASSES.items()}
        return cls(
            providers=providers,
            primary=LLM_PRIMARY_PROVIDER,
            fallbacks=list(LLM_FALLBACK_PROVIDERS),
            max_retries_per_provider=LLM_MAX_RETRIES_PER_PROVIDER,
        )

    def chain(self) -> list[str]:
        ordered: list[str] = []
        for name in [self.primary, *self.fallbacks]:
            if name and name not in ordered:
                ordered.append(name)
        return ordered

    def last_success(self) -> AttemptRecord | None:
        for record in reversed(self.attempts):
            if record.success:
                return record
        return None

    def generate(self, prompt: str) -> str:
        """Non-streaming generation. Always the same prompt across fallbacks."""
        self.attempts = []
        self._last_failure = None
        names = self.chain()
        for index, name in enumerate(names):
            provider = self.providers.get(name)
            if provider is None:
                _log(f"LLM provider skipped: provider={name} error_category=unknown_provider")
                continue
            if not provider.is_configured():
                self._record(provider, attempt=1, success=False, category=CATEGORY_INVALID_CONFIG)
                _log(
                    f"LLM provider failed: provider={name} error_category={CATEGORY_INVALID_CONFIG}"
                )
                continue
            if index > 0:
                _log(f"LLM fallback: from={names[index - 1]} to={name}")
            result = self._generate_with_retries(provider, prompt)
            if result is not None:
                return result
            if self._last_failure is not None and not self._last_failure.allow_fallback:
                break
        _log("LLM provider failed: provider=all error_category=all_failed")
        return GENERATION_UNAVAILABLE

    def stream(self, prompt: str) -> Iterator[str]:
        """
        Stream tokens from the first provider that starts successfully.

        Fallback is allowed only before any token is yielded.
        After tokens are emitted, a failure terminates the stream.
        """
        self.attempts = []
        self._last_failure = None
        names = self.chain()
        for index, name in enumerate(names):
            provider = self.providers.get(name)
            if provider is None:
                continue
            if not provider.is_configured():
                self._record(provider, attempt=1, success=False, category=CATEGORY_INVALID_CONFIG)
                _log(
                    f"LLM provider failed: provider={name} error_category={CATEGORY_INVALID_CONFIG}"
                )
                continue
            if index > 0:
                _log(f"LLM fallback: from={names[index - 1]} to={name}")
            emitted = False
            started = time.perf_counter()
            _log(f"LLM attempt: provider={name} model={provider.model_id()}")
            try:
                for chunk in provider.stream(prompt):
                    if chunk:
                        emitted = True
                        yield chunk
                latency = int((time.perf_counter() - started) * 1000)
                self._record(provider, attempt=1, success=True, latency_ms=latency)
                _log(f"LLM success: provider={name} latency_ms={latency}")
                return
            except Exception as exc:
                error = exc if isinstance(exc, LLMError) else LLMError(
                    safe_error_message(exc),
                    category="provider_unavailable",
                    provider=name,
                    retry_same=False,
                    allow_fallback=True,
                )
                latency = int((time.perf_counter() - started) * 1000)
                self._record(
                    provider,
                    attempt=1,
                    success=False,
                    category=error.category,
                    latency_ms=latency,
                    message=str(error),
                )
                _log(
                    f"LLM provider failed: provider={name} error_category={error.category}"
                )
                if emitted:
                    raise StreamInterruptedError(
                        f"{name} failed after tokens were sent",
                        provider=name,
                        category=CATEGORY_STREAM_INTERRUPTED,
                    ) from None
                if not error.allow_fallback:
                    break
        _log("LLM provider failed: provider=all error_category=all_failed")
        yield GENERATION_UNAVAILABLE

    def _generate_with_retries(self, provider: LLMProvider, prompt: str) -> str | None:
        max_attempts = 1 + self.max_retries_per_provider
        last_error: LLMError | None = None
        for attempt in range(1, max_attempts + 1):
            started = time.perf_counter()
            _log(
                f"LLM attempt: provider={provider.name} model={provider.model_id()}"
            )
            try:
                text = provider.generate(prompt)
                latency = int((time.perf_counter() - started) * 1000)
                self._record(provider, attempt=attempt, success=True, latency_ms=latency)
                _log(f"LLM success: provider={provider.name} latency_ms={latency}")
                return text
            except Exception as exc:
                error = exc if isinstance(exc, LLMError) else LLMError(
                    safe_error_message(exc),
                    category="provider_unavailable",
                    provider=provider.name,
                    retry_same=False,
                    allow_fallback=True,
                )
                last_error = error
                self._last_failure = error
                latency = int((time.perf_counter() - started) * 1000)
                self._record(
                    provider,
                    attempt=attempt,
                    success=False,
                    category=error.category,
                    latency_ms=latency,
                    message=str(error),
                )
                _log(
                    f"LLM provider failed: provider={provider.name} "
                    f"error_category={error.category}"
                )
                if error.retry_same and attempt < max_attempts:
                    continue
                if error.allow_fallback:
                    return None
                return None
        if last_error is not None and last_error.allow_fallback:
            return None
        return None

    def _record(
        self,
        provider: LLMProvider,
        *,
        attempt: int,
        success: bool,
        category: str | None = None,
        latency_ms: int = 0,
        message: str | None = None,
    ) -> None:
        self.attempts.append(
            AttemptRecord(
                provider=provider.name,
                model=provider.model_id(),
                latency_ms=latency_ms,
                attempt=attempt,
                success=success,
                error_category=category,
            )
        )
        if success:
            return
        try:
            from app_platform.ops.events import record_llm_event

            record_llm_event(
                provider=provider.name,
                category=category,
                message=message,
            )
        except Exception:
            return


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter.from_config()
    return _router


def reset_router() -> None:
    global _router
    _router = None


def set_router(router: LLMRouter) -> None:
    global _router
    _router = router
