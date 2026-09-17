"""Common LLM errors. Messages must never include API keys or auth headers."""

from __future__ import annotations


GENERATION_UNAVAILABLE = (
    "The answer service is temporarily unavailable. Please try again."
)

CATEGORY_TIMEOUT = "timeout"
CATEGORY_CONNECTION = "connection_error"
CATEGORY_RATE_LIMIT = "rate_limit"
CATEGORY_QUOTA = "quota_exhausted"
CATEGORY_PROVIDER_UNAVAILABLE = "provider_unavailable"
CATEGORY_MODEL_UNAVAILABLE = "model_unavailable"
CATEGORY_AUTH = "auth"
CATEGORY_MALFORMED = "malformed_request"
CATEGORY_INVALID_CONFIG = "invalid_configuration"
CATEGORY_INVALID_PARAMS = "invalid_request_parameters"
CATEGORY_STREAM_INTERRUPTED = "stream_interrupted"
CATEGORY_EMPTY = "empty_response"


class LLMError(Exception):
    def __init__(
        self,
        message: str,
        *,
        category: str,
        provider: str = "",
        retry_same: bool = False,
        allow_fallback: bool = True,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.category = category
        self.provider = provider
        self.retry_same = retry_same
        self.allow_fallback = allow_fallback
        self.status_code = status_code


class RetryableLLMError(LLMError):
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("retry_same", True)
        kwargs.setdefault("allow_fallback", True)
        super().__init__(message, **kwargs)


class NonRetryableLLMError(LLMError):
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("retry_same", False)
        kwargs.setdefault("allow_fallback", False)
        super().__init__(message, **kwargs)


class StreamInterruptedError(LLMError):
    """Tokens already reached the client; do not start another provider."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("category", CATEGORY_STREAM_INTERRUPTED)
        kwargs.setdefault("retry_same", False)
        kwargs.setdefault("allow_fallback", False)
        super().__init__(message, **kwargs)
