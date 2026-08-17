"""Provider router tests. No real LLM API calls."""

from __future__ import annotations

import json
import logging
import unittest
from collections.abc import Iterator
from unittest.mock import patch

import httpx

from llm.base import LLMProvider
from llm.errors import (
    CATEGORY_CONNECTION,
    CATEGORY_MALFORMED,
    CATEGORY_RATE_LIMIT,
    CATEGORY_TIMEOUT,
    GENERATION_UNAVAILABLE,
    NonRetryableLLMError,
    RetryableLLMError,
    StreamInterruptedError,
)
from llm.http_util import classify_http_error
from llm.providers.gemini import GeminiProvider
from llm.providers.mistral import MistralProvider
from llm.providers.openai_compat import OpenAICompatProvider
from llm.router import LLMRouter, reset_router, set_router
from llm.sanitize import redact_secrets
from llm_service import generate_response, generate_response_stream
from rag import ask_question


SECRET = "gsk_TESTKEY_NEVER_LOG_THIS_VALUE_12345"


class FakeProvider(LLMProvider):
    def __init__(
        self,
        name: str,
        *,
        model: str = "fake-model",
        configured: bool = True,
        responses: list[str] | None = None,
        errors: list[Exception] | None = None,
        stream_chunks: list[str] | None = None,
        error_before_stream: Exception | None = None,
        error_after_chunks: int | None = None,
    ):
        self.name = name
        self._model = model
        self._configured = configured
        self._responses = list(responses or [])
        self._errors = list(errors or [])
        self._stream_chunks = stream_chunks
        self._error_before_stream = error_before_stream
        self._error_after_chunks = error_after_chunks
        self.generate_prompts: list[str] = []
        self.stream_prompts: list[str] = []

    def model_id(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        return self._configured

    def generate(self, prompt: str) -> str:
        self.generate_prompts.append(prompt)
        if self._errors:
            raise self._errors.pop(0)
        if self._responses:
            return self._responses.pop(0)
        return f"{self.name}-ok"

    def stream(self, prompt: str) -> Iterator[str]:
        self.stream_prompts.append(prompt)
        if self._error_before_stream is not None:
            raise self._error_before_stream
        chunks = self._stream_chunks if self._stream_chunks is not None else [f"{self.name}-ok"]
        for index, chunk in enumerate(chunks):
            yield chunk
            if (
                self._error_after_chunks is not None
                and (index + 1) >= self._error_after_chunks
            ):
                raise RetryableLLMError(
                    "stream failed after tokens",
                    category=CATEGORY_TIMEOUT,
                    provider=self.name,
                )


def _rate_limit(provider: str) -> RetryableLLMError:
    return RetryableLLMError(
        "rate limited",
        category=CATEGORY_RATE_LIMIT,
        provider=provider,
    )


def _timeout(provider: str) -> RetryableLLMError:
    return RetryableLLMError(
        "timed out",
        category=CATEGORY_TIMEOUT,
        provider=provider,
    )


def _router(providers: dict[str, LLMProvider], primary: str, fallbacks: list[str]) -> LLMRouter:
    return LLMRouter(
        providers=providers,
        primary=primary,
        fallbacks=fallbacks,
        max_retries_per_provider=0,
    )


class TestProviderSelectionAndFallback(unittest.TestCase):
    def test_groq_success_does_not_fallback(self):
        groq = FakeProvider("groq", responses=["from groq"])
        gemini = FakeProvider("gemini", responses=["from gemini"])
        router = _router({"groq": groq, "gemini": gemini}, "groq", ["gemini"])
        result = router.generate("same prompt")
        self.assertEqual(result, "from groq")
        self.assertEqual(gemini.generate_prompts, [])
        self.assertEqual(router.last_success().provider, "groq")

    def test_groq_rate_limit_falls_back_to_gemini(self):
        groq = FakeProvider("groq", errors=[_rate_limit("groq")])
        gemini = FakeProvider("gemini", responses=["from gemini"])
        router = _router({"groq": groq, "gemini": gemini}, "groq", ["gemini"])
        result = router.generate("same prompt")
        self.assertEqual(result, "from gemini")
        self.assertEqual(groq.generate_prompts, ["same prompt"])
        self.assertEqual(gemini.generate_prompts, ["same prompt"])

    def test_groq_timeout_falls_back_to_gemini(self):
        groq = FakeProvider("groq", errors=[_timeout("groq")])
        gemini = FakeProvider("gemini", responses=["from gemini"])
        router = _router({"groq": groq, "gemini": gemini}, "groq", ["gemini"])
        self.assertEqual(router.generate("q"), "from gemini")

    def test_gemini_failure_falls_back_to_cerebras(self):
        groq = FakeProvider("groq", errors=[_rate_limit("groq")])
        gemini = FakeProvider("gemini", errors=[_timeout("gemini")])
        cerebras = FakeProvider("cerebras", responses=["from cerebras"])
        router = _router(
            {"groq": groq, "gemini": gemini, "cerebras": cerebras},
            "groq",
            ["gemini", "cerebras"],
        )
        self.assertEqual(router.generate("q"), "from cerebras")
        self.assertEqual(cerebras.generate_prompts, ["q"])

    def test_cerebras_failure_falls_back_to_openrouter(self):
        providers = {
            "groq": FakeProvider("groq", errors=[_rate_limit("groq")]),
            "gemini": FakeProvider("gemini", errors=[_timeout("gemini")]),
            "cerebras": FakeProvider("cerebras", errors=[_rate_limit("cerebras")]),
            "openrouter": FakeProvider("openrouter", responses=["from openrouter"]),
        }
        router = _router(providers, "groq", ["gemini", "cerebras", "openrouter"])
        self.assertEqual(router.generate("q"), "from openrouter")

    def test_openrouter_failure_falls_back_to_mistral(self):
        providers = {
            "groq": FakeProvider("groq", errors=[_rate_limit("groq")]),
            "gemini": FakeProvider("gemini", errors=[_timeout("gemini")]),
            "cerebras": FakeProvider("cerebras", errors=[_rate_limit("cerebras")]),
            "openrouter": FakeProvider("openrouter", errors=[_timeout("openrouter")]),
            "mistral": FakeProvider("mistral", responses=["from mistral"]),
        }
        router = _router(
            providers,
            "groq",
            ["gemini", "cerebras", "openrouter", "mistral"],
        )
        self.assertEqual(router.generate("q"), "from mistral")
        self.assertEqual(providers["mistral"].generate_prompts, ["q"])

    def test_all_providers_fail_returns_unavailable(self):
        providers = {
            "groq": FakeProvider("groq", errors=[_rate_limit("groq")]),
            "gemini": FakeProvider("gemini", errors=[_timeout("gemini")]),
            "cerebras": FakeProvider("cerebras", errors=[_rate_limit("cerebras")]),
            "openrouter": FakeProvider("openrouter", errors=[_timeout("openrouter")]),
            "mistral": FakeProvider("mistral", errors=[_rate_limit("mistral")]),
        }
        router = _router(
            providers,
            "groq",
            ["gemini", "cerebras", "openrouter", "mistral"],
        )
        result = router.generate("q")
        self.assertEqual(result, GENERATION_UNAVAILABLE)
        self.assertIsNone(router.last_success())

    def test_malformed_request_does_not_fallback(self):
        groq = FakeProvider(
            "groq",
            errors=[
                NonRetryableLLMError(
                    "bad request",
                    category=CATEGORY_MALFORMED,
                    provider="groq",
                )
            ],
        )
        gemini = FakeProvider("gemini", responses=["should not run"])
        router = _router({"groq": groq, "gemini": gemini}, "groq", ["gemini"])
        result = router.generate("q")
        self.assertEqual(result, GENERATION_UNAVAILABLE)
        self.assertEqual(gemini.generate_prompts, [])

    def test_same_prompt_passed_to_fallback_provider(self):
        prompt = "GROUNDED PROMPT v1"
        groq = FakeProvider("groq", errors=[_rate_limit("groq")])
        gemini = FakeProvider("gemini", responses=["ok"])
        router = _router({"groq": groq, "gemini": gemini}, "groq", ["gemini"])
        router.generate(prompt)
        self.assertEqual(groq.generate_prompts, [prompt])
        self.assertEqual(gemini.generate_prompts, [prompt])

    def test_provider_order_is_configurable(self):
        cerebras = FakeProvider("cerebras", responses=["from cerebras"])
        groq = FakeProvider("groq", responses=["from groq"])
        router = _router({"groq": groq, "cerebras": cerebras}, "cerebras", ["groq"])
        self.assertEqual(router.chain(), ["cerebras", "groq"])
        self.assertEqual(router.generate("q"), "from cerebras")
        self.assertEqual(groq.generate_prompts, [])

    def test_mistral_is_registered_and_selectable(self):
        from llm.providers import PROVIDER_CLASSES

        self.assertIn("mistral", PROVIDER_CLASSES)
        mistral = FakeProvider("mistral", responses=["from mistral"])
        groq = FakeProvider("groq", responses=["from groq"])
        router = _router({"groq": groq, "mistral": mistral}, "mistral", ["groq"])
        self.assertEqual(router.chain(), ["mistral", "groq"])
        self.assertEqual(router.generate("q"), "from mistral")
        self.assertEqual(groq.generate_prompts, [])


class TestStreamingFallback(unittest.TestCase):
    def test_streaming_success(self):
        groq = FakeProvider("groq", stream_chunks=["Hel", "lo"])
        gemini = FakeProvider("gemini", stream_chunks=["nope"])
        router = _router({"groq": groq, "gemini": gemini}, "groq", ["gemini"])
        text = "".join(router.stream("q"))
        self.assertEqual(text, "Hello")
        self.assertEqual(gemini.stream_prompts, [])

    def test_streaming_failure_before_tokens_falls_back(self):
        groq = FakeProvider("groq", error_before_stream=_rate_limit("groq"))
        gemini = FakeProvider("gemini", stream_chunks=["gemini-ok"])
        router = _router({"groq": groq, "gemini": gemini}, "groq", ["gemini"])
        text = "".join(router.stream("q"))
        self.assertEqual(text, "gemini-ok")
        self.assertEqual(gemini.stream_prompts, ["q"])

    def test_streaming_failure_after_tokens_does_not_concatenate(self):
        groq = FakeProvider(
            "groq",
            stream_chunks=["partial-A"],
            error_after_chunks=1,
        )
        gemini = FakeProvider("gemini", stream_chunks=["complete-B"])
        router = _router({"groq": groq, "gemini": gemini}, "groq", ["gemini"])
        chunks: list[str] = []
        with self.assertRaises(StreamInterruptedError):
            for chunk in router.stream("q"):
                chunks.append(chunk)
        self.assertEqual(chunks, ["partial-A"])
        self.assertEqual(gemini.stream_prompts, [])
        self.assertNotIn("complete-B", "".join(chunks))


class TestSecretsAndHttpErrors(unittest.TestCase):
    def test_api_keys_never_appear_in_redacted_errors(self):
        leaked = f"Authorization: Bearer {SECRET} failed for {SECRET}"
        redacted = redact_secrets(leaked)
        self.assertNotIn(SECRET, redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_router_logs_do_not_contain_api_keys(self):
        groq = FakeProvider(
            "groq",
            errors=[
                RetryableLLMError(
                    f"provider failed key={SECRET}",
                    category=CATEGORY_RATE_LIMIT,
                    provider="groq",
                )
            ],
        )
        gemini = FakeProvider("gemini", responses=["ok"])
        router = _router({"groq": groq, "gemini": gemini}, "groq", ["gemini"])
        logger = logging.getLogger("docusage.llm")
        with self.assertLogs(logger, level="INFO") as captured:
            router.generate("q")
        joined = "\n".join(captured.output)
        self.assertNotIn(SECRET, joined)

    def test_http_status_classification(self):
        rate = classify_http_error(429, "too many", provider="groq")
        self.assertEqual(rate.category, CATEGORY_RATE_LIMIT)
        self.assertTrue(rate.allow_fallback)
        timeout = classify_http_error(408, "", provider="groq")
        self.assertEqual(timeout.category, CATEGORY_TIMEOUT)
        auth = classify_http_error(401, "unauthorized", provider="groq")
        self.assertEqual(auth.category, "auth")
        self.assertTrue(auth.allow_fallback)
        self.assertFalse(auth.retry_same)
        missing = classify_http_error(404, "no model", provider="groq")
        self.assertEqual(missing.category, "model_unavailable")
        server = classify_http_error(503, "down", provider="groq")
        self.assertTrue(server.retry_same)
        malformed = classify_http_error(400, "bad json", provider="groq")
        self.assertIsInstance(malformed, NonRetryableLLMError)
        self.assertFalse(malformed.allow_fallback)
        quota = classify_http_error(429, "quota exhausted", provider="gemini")
        self.assertEqual(quota.category, "quota_exhausted")


class TestProviderHttpMocks(unittest.TestCase):
    def test_gemini_success_and_401(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertNotIn(SECRET, str(request.url))
            if request.headers.get("x-goog-api-key") != SECRET:
                return httpx.Response(401, json={"error": {"message": "nope"}})
            return httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": "gemini-ok"}]}}]},
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = GeminiProvider(api_key=SECRET, model="gemini-2.0-flash", client=client)
        self.assertEqual(provider.generate("hello"), "gemini-ok")
        denied = GeminiProvider(api_key="wrong", model="gemini-2.0-flash", client=client)
        with self.assertRaises(Exception) as ctx:
            denied.generate("hello")
        self.assertNotIn(SECRET, str(ctx.exception))

    def test_openai_compat_timeout_and_500(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if b"boom" in request.content:
                return httpx.Response(500, json={"error": {"message": "down"}})
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "compat-ok"}}]},
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = OpenAICompatProvider(
            name="cerebras",
            api_key=SECRET,
            model="llama3.1-8b",
            base_url="https://api.cerebras.ai/v1",
            timeout=5,
            client=client,
        )
        self.assertEqual(provider.generate("hi"), "compat-ok")
        with self.assertRaises(RetryableLLMError) as ctx:
            provider.generate("boom")
        self.assertEqual(ctx.exception.category, "provider_unavailable")
        self.assertNotIn(SECRET, str(ctx.exception))

    def test_connection_failure(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = GeminiProvider(api_key=SECRET, model="gemini-2.0-flash", client=client)
        with self.assertRaises(RetryableLLMError) as ctx:
            provider.generate("hi")
        self.assertEqual(ctx.exception.category, CATEGORY_CONNECTION)

    def test_mistral_success_stream_and_429(self):
        secret = "mistral_TESTKEY_NEVER_LOG_THIS_VALUE"

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.host, "api.mistral.ai")
            self.assertTrue(str(request.url.path).endswith("/chat/completions"))
            self.assertNotIn(secret, str(request.url))
            body = json.loads(request.content.decode("utf-8"))
            self.assertEqual(body.get("model"), "mistral-small-latest")
            if request.headers.get("Authorization") != f"Bearer {secret}":
                return httpx.Response(401, json={"message": "unauthorized"})
            if body.get("messages", [{}])[0].get("content") == "rate-limit":
                return httpx.Response(429, json={"message": "too many requests"})
            if body.get("stream"):
                return httpx.Response(
                    200,
                    headers={"Content-Type": "text/event-stream"},
                    content=(
                        b'data: {"choices":[{"delta":{"content":"mis"}}]}\n\n'
                        b'data: {"choices":[{"delta":{"content":"tral"}}]}\n\n'
                        b"data: [DONE]\n\n"
                    ),
                )
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "mistral-ok"}}]},
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = MistralProvider(
            api_key=secret,
            model="mistral-small-latest",
            client=client,
        )
        self.assertEqual(provider.generate("hello"), "mistral-ok")
        self.assertEqual("".join(provider.stream("hello")), "mistral")
        with self.assertRaises(RetryableLLMError) as ctx:
            provider.generate("rate-limit")
        self.assertEqual(ctx.exception.category, CATEGORY_RATE_LIMIT)
        self.assertNotIn(secret, str(ctx.exception))
        groq = FakeProvider("groq", errors=[_rate_limit("groq")])
        router = _router({"groq": groq, "mistral": provider}, "groq", ["mistral"])
        self.assertEqual(router.generate("hello"), "mistral-ok")


class TestRagEvidenceUnchanged(unittest.TestCase):
    def tearDown(self):
        reset_router()

    def _retrieval(self):
        return {
            "chunks": ["Entropy measures uncertainty in the document."],
            "distances": [0.2],
            "metadata": [
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page_number": 4,
                }
            ],
            "ids": ["doc-a_1"],
            "relevances": [90],
            "reranker_scores": [2.0],
            "rerank_fallback": False,
        }

    def test_provider_failure_does_not_alter_rag_evidence(self):
        groq = FakeProvider("groq", errors=[_rate_limit("groq")])
        gemini = FakeProvider("gemini", responses=["Entropy measures uncertainty."])
        router = _router({"groq": groq, "gemini": gemini}, "groq", ["gemini"])
        set_router(router)
        retrieval = self._retrieval()
        with patch("rag.retrieve_candidates", return_value=retrieval) as mock_retrieve:
            result = ask_question("What is entropy?", None, ["doc-a"], generate=True)
        mock_retrieve.assert_called_once()
        self.assertEqual(mock_retrieve.call_args.args[0], "What is entropy?")
        self.assertEqual(result["answer"], "Entropy measures uncertainty.")
        self.assertEqual(result["sources"][0]["page"], 4)
        self.assertIn("Entropy measures uncertainty in the document.", result["prompt"])
        self.assertEqual(groq.generate_prompts, gemini.generate_prompts)
        self.assertEqual(len(groq.generate_prompts), 1)
        self.assertIn("What is entropy?", groq.generate_prompts[0])
        self.assertIn("Entropy measures uncertainty in the document.", groq.generate_prompts[0])

    def test_facade_uses_router(self):
        groq = FakeProvider("groq", responses=["facade-ok"])
        set_router(_router({"groq": groq}, "groq", []))
        self.assertEqual(generate_response("hello"), "facade-ok")
        self.assertEqual("".join(generate_response_stream("hello")), "groq-ok")


class TestUnconfiguredProviderSkipped(unittest.TestCase):
    def test_missing_key_skips_to_next_provider(self):
        groq = FakeProvider("groq", configured=False)
        gemini = FakeProvider("gemini", responses=["from gemini"])
        router = _router({"groq": groq, "gemini": gemini}, "groq", ["gemini"])
        self.assertEqual(router.generate("q"), "from gemini")
        self.assertEqual(groq.generate_prompts, [])


if __name__ == "__main__":
    unittest.main()
