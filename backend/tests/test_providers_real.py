"""Tests for real provider adapters (Gemini, Groq, OpenRouter, Ollama),
the ProviderRegistry, and the LLM verifier_type API integration.

All tests use httpx.MockTransport so NO real API keys or internet access
are required. The existing 53 tests are not modified.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.session import get_db
from app.main import create_app
from app.providers.base import ErrorCategory, RetryPolicy
from app.providers.gemini import GeminiProvider
from app.providers.groq import GroqProvider
from app.providers.mock import UnconfiguredProvider
from app.providers.ollama import OllamaProvider
from app.providers.openrouter import OpenRouterProvider
from app.providers.registry import IMPLEMENTED_PROVIDER_IDS, ProviderRegistry
from tests.helpers import run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _no_sleep(_):
    """Instant sleep stand-in so retry tests complete fast."""
    return asyncio.sleep(0)


def _mock_client(responses: list[tuple[int, dict]]) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient backed by a scripted MockTransport."""
    responses_iter = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        status_code, body = next(responses_iter)
        return httpx.Response(status_code, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _client_with_error(exc: Exception) -> httpx.AsyncClient:
    """Client that raises a transport exception on every request."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# Gemini Provider Tests
# ---------------------------------------------------------------------------

GEMINI_OK_BODY = {
    "candidates": [{"content": {"parts": [{"text": "Paris is the capital of France."}]}, "finishReason": "STOP"}],
    "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 8},
}

GEMINI_EMPTY_BODY = {
    "candidates": [{"content": {"parts": [{"text": ""}]}, "finishReason": "STOP"}],
    "usageMetadata": {},
}

GEMINI_SAFETY_BODY = {
    "candidates": [{"finishReason": "SAFETY"}],
}

GEMINI_AUTH_BODY = {
    "error": {"code": 401, "message": "API key not valid.", "status": "UNAUTHENTICATED"},
}

GEMINI_RATE_BODY = {
    "error": {"code": 429, "message": "Resource has been exhausted.", "status": "RESOURCE_EXHAUSTED"},
}

GEMINI_SERVER_BODY = {
    "error": {"code": 503, "message": "The service is currently unavailable.", "status": "UNAVAILABLE"},
}


class GeminiProviderTests(unittest.TestCase):
    def _make(self, responses, attempts=1):
        return GeminiProvider(
            api_key="AIzaFAKEKEY00000000000000",
            model="gemini-1.5-flash",
            retry=RetryPolicy(max_attempts=attempts),
            http_client=_mock_client(responses),
            sleep=_no_sleep,
        )

    def test_successful_response(self):
        p = self._make([(200, GEMINI_OK_BODY)])
        r = run(p.generate_answer("What is the capital of France?"))
        self.assertTrue(r.ok)
        self.assertEqual(r.text, "Paris is the capital of France.")
        self.assertEqual(r.input_tokens, 10)
        self.assertEqual(r.output_tokens, 8)
        self.assertEqual(r.provider, "gemini")
        self.assertEqual(r.model, "gemini-1.5-flash")

    def test_system_prompt_accepted(self):
        p = self._make([(200, GEMINI_OK_BODY)])
        r = run(p.generate_answer("prompt", system="You are a helpful assistant."))
        self.assertTrue(r.ok)

    def test_missing_usage_metadata(self):
        body = {"candidates": [{"content": {"parts": [{"text": "hello"}]}, "finishReason": "STOP"}]}
        p = self._make([(200, body)])
        r = run(p.generate_answer("hi"))
        self.assertTrue(r.ok)
        self.assertIsNone(r.input_tokens)
        self.assertIsNone(r.output_tokens)

    def test_auth_failure_never_retried(self):
        p = self._make([(401, GEMINI_AUTH_BODY)] * 3, attempts=3)
        r = run(p.generate_answer("hi"))
        self.assertFalse(r.ok)
        self.assertEqual(r.error_category, ErrorCategory.AUTHENTICATION)
        self.assertEqual(r.attempts, 1)  # auth errors must NOT be retried

    def test_rate_limit_retried(self):
        p = self._make([(429, GEMINI_RATE_BODY), (200, GEMINI_OK_BODY)], attempts=3)
        r = run(p.generate_answer("hi"))
        self.assertTrue(r.ok)
        self.assertEqual(r.attempts, 2)

    def test_server_error_retried(self):
        p = self._make([(503, GEMINI_SERVER_BODY), (200, GEMINI_OK_BODY)], attempts=3)
        r = run(p.generate_answer("hi"))
        self.assertTrue(r.ok)
        self.assertEqual(r.attempts, 2)

    def test_timeout(self):
        async def hang(_req):
            await asyncio.sleep(3600)

        client = httpx.AsyncClient(transport=httpx.MockTransport(hang))
        p = GeminiProvider(api_key="AIzaFAKE", model="gemini-1.5-flash",
                           retry=RetryPolicy(max_attempts=1), http_client=client, sleep=_no_sleep)
        r = run(p.generate_answer("hi", timeout_s=0.05))
        self.assertEqual(r.error_category, ErrorCategory.TIMEOUT)

    def test_connection_failure(self):
        p = GeminiProvider(api_key="AIzaFAKE", model="gemini-1.5-flash",
                           retry=RetryPolicy(max_attempts=1),
                           http_client=_client_with_error(httpx.ConnectError("refused")),
                           sleep=_no_sleep)
        r = run(p.generate_answer("hi"))
        self.assertEqual(r.error_category, ErrorCategory.PROVIDER_OUTAGE)

    def test_malformed_json_response(self):
        def handler(req):
            return httpx.Response(200, content=b"not-json", headers={"Content-Type": "application/json"})
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        p = GeminiProvider(api_key="AIzaFAKE", model="gemini-1.5-flash",
                           retry=RetryPolicy(max_attempts=1), http_client=client, sleep=_no_sleep)
        r = run(p.generate_answer("hi"))
        self.assertEqual(r.error_category, ErrorCategory.MALFORMED_RESPONSE)

    def test_empty_response_text(self):
        p = self._make([(200, GEMINI_EMPTY_BODY)], attempts=1)
        r = run(p.generate_answer("hi"))
        self.assertEqual(r.error_category, ErrorCategory.MALFORMED_RESPONSE)

    def test_safety_block(self):
        p = self._make([(200, GEMINI_SAFETY_BODY)], attempts=1)
        r = run(p.generate_answer("hi"))
        self.assertFalse(r.ok)
        self.assertEqual(r.error_category, ErrorCategory.BAD_REQUEST)

    def test_missing_candidates(self):
        p = self._make([(200, {"usageMetadata": {}})], attempts=1)
        r = run(p.generate_answer("hi"))
        self.assertEqual(r.error_category, ErrorCategory.MALFORMED_RESPONSE)

    def test_error_message_does_not_contain_api_key(self):
        p = self._make([(401, GEMINI_AUTH_BODY)], attempts=1)
        r = run(p.generate_answer("hi"))
        self.assertFalse(r.ok)
        # The raw API key must never leak into error messages
        self.assertNotIn("AIzaFAKEKEY00000000000000", r.error_message or "")

    def test_error_message_redacts_url_with_key(self):
        url_with_key = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=AIzaFAKEKEY00000000000000"
        err_body = {"error": {"code": 400, "message": f"Bad request to {url_with_key}"}}
        p = self._make([(400, err_body)], attempts=1)
        r = run(p.generate_answer("hi"))
        self.assertFalse(r.ok)
        self.assertNotIn("AIzaFAKEKEY00000000000000", r.error_message or "")
        self.assertIn("key=[REDACTED]", r.error_message or "")

    def test_missing_api_key_raises(self):
        with self.assertRaises(ValueError):
            GeminiProvider(api_key="", model="gemini-1.5-flash")

    def test_missing_model_raises(self):
        with self.assertRaises(ValueError):
            GeminiProvider(api_key="AIzaFAKE", model="")


# ---------------------------------------------------------------------------
# Groq Provider Tests
# ---------------------------------------------------------------------------

GROQ_OK_BODY = {
    "choices": [{"message": {"role": "assistant", "content": "Paris is in France."}}],
    "usage": {"prompt_tokens": 12, "completion_tokens": 5},
    "model": "llama-3.1-8b-instant",
}

GROQ_EMPTY_BODY = {
    "choices": [{"message": {"role": "assistant", "content": ""}}],
    "usage": {},
}

GROQ_AUTH_BODY = {"error": {"message": "Invalid API Key.", "type": "invalid_request_error"}}
GROQ_RATE_BODY = {"error": {"message": "Rate limit exceeded.", "type": "rate_limit_error"}}


class GroqProviderTests(unittest.TestCase):
    def _make(self, responses, attempts=1):
        return GroqProvider(
            api_key="gsk_FAKEKEY0000000000000000000",
            model="llama-3.1-8b-instant",
            retry=RetryPolicy(max_attempts=attempts),
            http_client=_mock_client(responses),
            sleep=_no_sleep,
        )

    def test_successful_response(self):
        p = self._make([(200, GROQ_OK_BODY)])
        r = run(p.generate_answer("Where is Paris?"))
        self.assertTrue(r.ok)
        self.assertEqual(r.text, "Paris is in France.")
        self.assertEqual(r.input_tokens, 12)
        self.assertEqual(r.output_tokens, 5)
        self.assertEqual(r.provider, "groq")

    def test_system_prompt_accepted(self):
        p = self._make([(200, GROQ_OK_BODY)])
        r = run(p.generate_answer("prompt", system="You are helpful."))
        self.assertTrue(r.ok)

    def test_missing_usage(self):
        body = {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
        p = self._make([(200, body)])
        r = run(p.generate_answer("hi"))
        self.assertTrue(r.ok)
        self.assertIsNone(r.input_tokens)
        self.assertIsNone(r.output_tokens)

    def test_auth_failure_not_retried(self):
        p = self._make([(401, GROQ_AUTH_BODY)] * 3, attempts=3)
        r = run(p.generate_answer("hi"))
        self.assertFalse(r.ok)
        self.assertEqual(r.error_category, ErrorCategory.AUTHENTICATION)
        self.assertEqual(r.attempts, 1)

    def test_rate_limit_retried(self):
        p = self._make([(429, GROQ_RATE_BODY), (200, GROQ_OK_BODY)], attempts=3)
        r = run(p.generate_answer("hi"))
        self.assertTrue(r.ok)
        self.assertEqual(r.attempts, 2)

    def test_bad_request(self):
        body = {"error": {"message": "Invalid model.", "type": "invalid_request_error"}}
        p = self._make([(400, body)], attempts=1)
        r = run(p.generate_answer("hi"))
        self.assertEqual(r.error_category, ErrorCategory.BAD_REQUEST)
        self.assertEqual(r.attempts, 1)  # 400s must not be retried

    def test_empty_response(self):
        p = self._make([(200, GROQ_EMPTY_BODY)], attempts=1)
        r = run(p.generate_answer("hi"))
        self.assertEqual(r.error_category, ErrorCategory.MALFORMED_RESPONSE)

    def test_malformed_json(self):
        def handler(req):
            return httpx.Response(200, content=b"garbage", headers={"Content-Type": "application/json"})
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        p = GroqProvider(api_key="gsk_FAKE", model="llama3",
                         retry=RetryPolicy(max_attempts=1), http_client=client, sleep=_no_sleep)
        r = run(p.generate_answer("hi"))
        self.assertEqual(r.error_category, ErrorCategory.MALFORMED_RESPONSE)

    def test_connection_failure(self):
        p = GroqProvider(api_key="gsk_FAKE", model="llama3",
                         retry=RetryPolicy(max_attempts=1),
                         http_client=_client_with_error(httpx.ConnectError("refused")),
                         sleep=_no_sleep)
        r = run(p.generate_answer("hi"))
        self.assertEqual(r.error_category, ErrorCategory.PROVIDER_OUTAGE)

    def test_missing_api_key_raises(self):
        with self.assertRaises(ValueError):
            GroqProvider(api_key="", model="llama3")

    def test_missing_model_raises(self):
        with self.assertRaises(ValueError):
            GroqProvider(api_key="gsk_FAKE", model="")

    def test_api_key_not_in_error_message(self):
        p = self._make([(401, GROQ_AUTH_BODY)], attempts=1)
        r = run(p.generate_answer("hi"))
        self.assertNotIn("gsk_FAKEKEY0000000000000000000", r.error_message or "")


# ---------------------------------------------------------------------------
# OpenRouter Provider Tests
# ---------------------------------------------------------------------------

OPENROUTER_OK_BODY = {
    "choices": [{"message": {"role": "assistant", "content": "The Eiffel Tower is in Paris."}}],
    "usage": {"prompt_tokens": 20, "completion_tokens": 9},
    "model": "openai/gpt-4o-mini",
}

OPENROUTER_AUTH_BODY = {"error": {"message": "No auth token provided.", "code": 401}}
OPENROUTER_RATE_BODY = {"error": {"message": "Rate limit exceeded.", "code": 429}}


class OpenRouterProviderTests(unittest.TestCase):
    def _make(self, responses, attempts=1):
        return OpenRouterProvider(
            api_key="sk-or-FAKEKEY000000000000000",
            model="openai/gpt-4o-mini",
            retry=RetryPolicy(max_attempts=attempts),
            http_client=_mock_client(responses),
            sleep=_no_sleep,
        )

    def test_successful_response(self):
        p = self._make([(200, OPENROUTER_OK_BODY)])
        r = run(p.generate_answer("Where is the Eiffel Tower?"))
        self.assertTrue(r.ok)
        self.assertEqual(r.text, "The Eiffel Tower is in Paris.")
        self.assertEqual(r.input_tokens, 20)
        self.assertEqual(r.output_tokens, 9)
        self.assertEqual(r.provider, "openrouter")

    def test_system_prompt_accepted(self):
        p = self._make([(200, OPENROUTER_OK_BODY)])
        r = run(p.generate_answer("prompt", system="You are a fact-checker."))
        self.assertTrue(r.ok)

    def test_auth_failure_not_retried(self):
        p = self._make([(401, OPENROUTER_AUTH_BODY)] * 3, attempts=3)
        r = run(p.generate_answer("hi"))
        self.assertFalse(r.ok)
        self.assertEqual(r.error_category, ErrorCategory.AUTHENTICATION)
        self.assertEqual(r.attempts, 1)

    def test_rate_limit_retried(self):
        p = self._make([(429, OPENROUTER_RATE_BODY), (200, OPENROUTER_OK_BODY)], attempts=3)
        r = run(p.generate_answer("hi"))
        self.assertTrue(r.ok)
        self.assertEqual(r.attempts, 2)

    def test_server_error_retried(self):
        server_body = {"error": {"message": "Internal server error.", "code": 500}}
        p = self._make([(500, server_body), (200, OPENROUTER_OK_BODY)], attempts=3)
        r = run(p.generate_answer("hi"))
        self.assertTrue(r.ok)
        self.assertEqual(r.attempts, 2)

    def test_missing_choices(self):
        p = self._make([(200, {"usage": {}})], attempts=1)
        r = run(p.generate_answer("hi"))
        self.assertEqual(r.error_category, ErrorCategory.MALFORMED_RESPONSE)

    def test_empty_response(self):
        body = {"choices": [{"message": {"role": "assistant", "content": ""}}], "usage": {}}
        p = self._make([(200, body)], attempts=1)
        r = run(p.generate_answer("hi"))
        self.assertEqual(r.error_category, ErrorCategory.MALFORMED_RESPONSE)

    def test_connection_failure(self):
        p = OpenRouterProvider(api_key="sk-or-FAKE", model="openai/gpt-4o",
                               retry=RetryPolicy(max_attempts=1),
                               http_client=_client_with_error(httpx.ConnectError("refused")),
                               sleep=_no_sleep)
        r = run(p.generate_answer("hi"))
        self.assertEqual(r.error_category, ErrorCategory.PROVIDER_OUTAGE)

    def test_missing_api_key_raises(self):
        with self.assertRaises(ValueError):
            OpenRouterProvider(api_key="", model="openai/gpt-4o")

    def test_missing_model_raises(self):
        with self.assertRaises(ValueError):
            OpenRouterProvider(api_key="sk-or-FAKE", model="")

    def test_api_key_not_in_error_message(self):
        p = self._make([(401, OPENROUTER_AUTH_BODY)], attempts=1)
        r = run(p.generate_answer("hi"))
        self.assertNotIn("sk-or-FAKEKEY000000000000000", r.error_message or "")


# ---------------------------------------------------------------------------
# Ollama Provider Tests
# ---------------------------------------------------------------------------

OLLAMA_OK_BODY = {
    "response": "The sky is blue.",
    "done": True,
    "prompt_eval_count": 7,
    "eval_count": 4,
}

OLLAMA_EMPTY_BODY = {"response": "", "done": True}

OLLAMA_NOT_FOUND_BODY = {"error": "model 'badmodel' not found"}


class OllamaProviderTests(unittest.TestCase):
    def _make(self, responses, attempts=1):
        return OllamaProvider(
            model="llama3.1",
            base_url="http://localhost:11434",
            retry=RetryPolicy(max_attempts=attempts),
            http_client=_mock_client(responses),
            sleep=_no_sleep,
        )

    def test_successful_response(self):
        p = self._make([(200, OLLAMA_OK_BODY)])
        r = run(p.generate_answer("Why is the sky blue?"))
        self.assertTrue(r.ok)
        self.assertEqual(r.text, "The sky is blue.")
        self.assertEqual(r.input_tokens, 7)
        self.assertEqual(r.output_tokens, 4)
        self.assertEqual(r.provider, "ollama")

    def test_system_prompt_accepted(self):
        p = self._make([(200, OLLAMA_OK_BODY)])
        r = run(p.generate_answer("prompt", system="You are a scientist."))
        self.assertTrue(r.ok)

    def test_missing_token_counts(self):
        body = {"response": "hello", "done": True}
        p = self._make([(200, body)])
        r = run(p.generate_answer("hi"))
        self.assertTrue(r.ok)
        self.assertIsNone(r.input_tokens)
        self.assertIsNone(r.output_tokens)

    def test_model_not_found(self):
        p = self._make([(404, OLLAMA_NOT_FOUND_BODY)], attempts=1)
        r = run(p.generate_answer("hi"))
        self.assertFalse(r.ok)
        # 404 from Ollama = bad request (model not pulled)
        self.assertIn(r.error_category, (ErrorCategory.BAD_REQUEST, ErrorCategory.UNKNOWN))

    def test_server_error_retried(self):
        server_body = {"error": "internal error"}
        p = self._make([(500, server_body), (200, OLLAMA_OK_BODY)], attempts=3)
        r = run(p.generate_answer("hi"))
        self.assertTrue(r.ok)
        self.assertEqual(r.attempts, 2)

    def test_connection_failure_is_provider_outage(self):
        """Ollama not running should report PROVIDER_OUTAGE with a helpful message."""
        p = OllamaProvider(model="llama3.1",
                           retry=RetryPolicy(max_attempts=1),
                           http_client=_client_with_error(httpx.ConnectError("connection refused")),
                           sleep=_no_sleep)
        r = run(p.generate_answer("hi"))
        self.assertEqual(r.error_category, ErrorCategory.PROVIDER_OUTAGE)

    def test_empty_response(self):
        p = self._make([(200, OLLAMA_EMPTY_BODY)], attempts=1)
        r = run(p.generate_answer("hi"))
        self.assertEqual(r.error_category, ErrorCategory.MALFORMED_RESPONSE)

    def test_missing_response_field(self):
        p = self._make([(200, {"done": True})], attempts=1)
        r = run(p.generate_answer("hi"))
        self.assertEqual(r.error_category, ErrorCategory.MALFORMED_RESPONSE)

    def test_malformed_json(self):
        def handler(req):
            return httpx.Response(200, content=b"bad", headers={"Content-Type": "application/json"})
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        p = OllamaProvider(model="llama3.1", retry=RetryPolicy(max_attempts=1),
                           http_client=client, sleep=_no_sleep)
        r = run(p.generate_answer("hi"))
        self.assertEqual(r.error_category, ErrorCategory.MALFORMED_RESPONSE)

    def test_timeout(self):
        async def hang(_req):
            await asyncio.sleep(3600)

        client = httpx.AsyncClient(transport=httpx.MockTransport(hang))
        p = OllamaProvider(model="llama3.1", retry=RetryPolicy(max_attempts=1),
                           http_client=client, sleep=_no_sleep)
        r = run(p.generate_answer("hi", timeout_s=0.05))
        self.assertEqual(r.error_category, ErrorCategory.TIMEOUT)

    def test_missing_model_raises(self):
        with self.assertRaises(ValueError):
            OllamaProvider(model="")

    def test_default_base_url(self):
        """OllamaProvider defaults to localhost:11434 when base_url is empty."""
        p = OllamaProvider(model="llama3.1", base_url="")
        self.assertIn("localhost:11434", p._base_url)


# ---------------------------------------------------------------------------
# Provider Registry Tests
# ---------------------------------------------------------------------------

class ProviderRegistryTests(unittest.TestCase):
    def test_implemented_ids_are_correct(self):
        self.assertEqual(IMPLEMENTED_PROVIDER_IDS, frozenset({"gemini", "groq", "openrouter", "ollama"}))

    def test_unconfigured_env_returns_unconfigured_providers(self):
        registry = ProviderRegistry.from_env(env={})
        for pid in ("gemini", "groq", "openrouter", "ollama"):
            p = registry.get(pid)
            self.assertIsInstance(p, UnconfiguredProvider, f"{pid} should be unconfigured")
            self.assertFalse(registry.is_configured(pid))

    def test_configured_gemini_returns_gemini_provider(self):
        env = {"GEMINI_API_KEY": "AIzaFAKE0000000000000000", "GEMINI_MODEL": "gemini-1.5-flash"}
        registry = ProviderRegistry.from_env(env=env)
        p = registry.get("gemini")
        self.assertIsInstance(p, GeminiProvider)
        self.assertTrue(registry.is_configured("gemini"))
        self.assertEqual(p.model, "gemini-1.5-flash")

    def test_configured_groq_returns_groq_provider(self):
        env = {"GROQ_API_KEY": "gsk_FAKEKEY000000000000000000", "GROQ_MODEL": "llama-3.1-8b-instant"}
        registry = ProviderRegistry.from_env(env=env)
        p = registry.get("groq")
        self.assertIsInstance(p, GroqProvider)
        self.assertTrue(registry.is_configured("groq"))

    def test_configured_openrouter_returns_openrouter_provider(self):
        env = {"OPENROUTER_API_KEY": "sk-or-FAKEKEY000", "OPENROUTER_MODEL": "openai/gpt-4o-mini"}
        registry = ProviderRegistry.from_env(env=env)
        p = registry.get("openrouter")
        self.assertIsInstance(p, OpenRouterProvider)
        self.assertTrue(registry.is_configured("openrouter"))

    def test_configured_ollama_returns_ollama_provider(self):
        env = {"OLLAMA_BASE_URL": "http://localhost:11434", "OLLAMA_MODEL": "llama3.1"}
        registry = ProviderRegistry.from_env(env=env)
        p = registry.get("ollama")
        self.assertIsInstance(p, OllamaProvider)
        self.assertTrue(registry.is_configured("ollama"))
        self.assertEqual(p._base_url, "http://localhost:11434")

    def test_ollama_only_needs_model_env(self):
        """Ollama is keyless; only OLLAMA_MODEL is required."""
        env = {"OLLAMA_MODEL": "mistral"}
        registry = ProviderRegistry.from_env(env=env)
        p = registry.get("ollama")
        self.assertIsInstance(p, OllamaProvider)

    def test_partial_config_returns_unconfigured(self):
        """Only key without model → unconfigured."""
        env = {"GEMINI_API_KEY": "AIzaFAKE"}  # no GEMINI_MODEL
        registry = ProviderRegistry.from_env(env=env)
        self.assertFalse(registry.is_configured("gemini"))
        self.assertIsInstance(registry.get("gemini"), UnconfiguredProvider)

    def test_unknown_provider_returns_unconfigured(self):
        registry = ProviderRegistry.from_env(env={})
        p = registry.get("nonexistent_provider")
        self.assertIsInstance(p, UnconfiguredProvider)

    def test_registry_keys_never_exposed(self):
        """API keys stored in registry providers must never appear in their .model attribute or name."""
        env = {"GEMINI_API_KEY": "AIzaVERYSECRETKEY", "GEMINI_MODEL": "gemini-1.5-flash"}
        registry = ProviderRegistry.from_env(env=env)
        p = registry.get("gemini")
        self.assertNotIn("AIzaVERYSECRETKEY", p.name)
        self.assertNotIn("AIzaVERYSECRETKEY", str(p.model))

    def test_all_providers_present(self):
        """Registry should contain entries for every PROVIDER_SPEC."""
        registry = ProviderRegistry.from_env(env={})
        all_p = registry.all_providers()
        for pid in ("gemini", "groq", "openrouter", "openai", "anthropic", "xai", "ollama"):
            self.assertIn(pid, all_p)


# ---------------------------------------------------------------------------
# Adapter Status: IMPLEMENTED_ADAPTERS in config
# ---------------------------------------------------------------------------

class AdapterStatusTests(unittest.TestCase):
    def test_implemented_adapters_reflects_milestone_3a(self):
        from app.core.config import IMPLEMENTED_ADAPTERS
        for pid in ("gemini", "groq", "openrouter", "ollama"):
            self.assertIn(pid, IMPLEMENTED_ADAPTERS)

    def test_provider_statuses_adapter_available_flag(self):
        from app.core.config import provider_statuses
        statuses = provider_statuses(env={})
        by_name = {s["provider"]: s for s in statuses}
        for pid in ("gemini", "groq", "openrouter", "ollama"):
            self.assertTrue(by_name[pid]["adapter_available"],
                            f"{pid} should report adapter_available=True")
        # Providers without Milestone 3A adapters should still be false
        for pid in ("openai", "anthropic", "xai"):
            self.assertFalse(by_name[pid]["adapter_available"])


# ---------------------------------------------------------------------------
# API Integration Tests (LLM verifier_type via FastAPI TestClient)
# ---------------------------------------------------------------------------

def _make_verdict(claim_id, cls, supporting=(), reasoning="matches source", confidence=0.9):
    return json.dumps({
        "claim_id": claim_id,
        "classification": cls,
        "supporting": [{"source_id": s, "excerpt": e} for s, e in supporting],
        "contradicting": [],
        "reasoning": reasoning,
        "confidence": confidence,
    })


class LLMVerifierTypeApiTests(unittest.TestCase):
    """Tests for verifier_type='llm' via the FastAPI evaluation endpoint.

    Uses a MockProvider injected via the registry override pattern so no
    real provider credentials or network are required.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(self.db_url, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.app = create_app()

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_llm_verifier_type_missing_provider_id_returns_400(self):
        payload = {
            "question": "q",
            "answer": "The Eiffel Tower was completed in 1889.",
            "sources": [{"id": "S1", "text": "The Eiffel Tower was completed in 1889."}],
            "config": {"verifier_type": "llm"},  # no provider_id
        }
        res = self.client.post("/api/evaluations", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("provider_id is required", res.json()["detail"])

    def test_llm_verifier_type_unconfigured_provider_returns_400(self):
        """When the requested provider is not configured, the API returns 400 with a clear message."""
        payload = {
            "question": "q",
            "answer": "The Eiffel Tower was completed in 1889.",
            "sources": [{"id": "S1", "text": "The Eiffel Tower was completed in 1889."}],
            "config": {"verifier_type": "llm", "provider_id": "gemini"},
            # No GEMINI_API_KEY in env, so registry will return UnconfiguredProvider
        }
        # Make sure env is clean for this test
        import os
        original_key = os.environ.pop("GEMINI_API_KEY", None)
        original_model = os.environ.pop("GEMINI_MODEL", None)
        try:
            res = self.client.post("/api/evaluations", json=payload)
            self.assertEqual(res.status_code, 400)
            self.assertIn("not configured", res.json()["detail"])
        finally:
            if original_key:
                os.environ["GEMINI_API_KEY"] = original_key
            if original_model:
                os.environ["GEMINI_MODEL"] = original_model

    def test_llm_verifier_type_unknown_provider_returns_400(self):
        payload = {
            "question": "q",
            "answer": "The Eiffel Tower was completed in 1889.",
            "sources": [{"id": "S1", "text": "The Eiffel Tower was completed in 1889."}],
            "config": {"verifier_type": "llm", "provider_id": "nonexistent_provider"},
        }
        res = self.client.post("/api/evaluations", json=payload)
        self.assertEqual(res.status_code, 400)

    def test_rule_based_still_works_after_schema_extension(self):
        """Ensure existing rule_based verifier_type continues to work unchanged."""
        payload = {
            "question": "When was the Eiffel Tower built?",
            "answer": "The Eiffel Tower was completed in 1889.",
            "sources": [{"id": "S1", "text": "The Eiffel Tower was completed in 1889."}],
            "config": {"verifier_type": "rule_based"},
        }
        res = self.client.post("/api/evaluations", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["verifications"][0]["classification"], "SUPPORTED")

    def test_providers_endpoint_shows_adapter_available_for_milestone_3a(self):
        res = self.client.get("/api/providers")
        self.assertEqual(res.status_code, 200)
        by_name = {p["provider"]: p for p in res.json()["providers"]}
        for pid in ("gemini", "groq", "openrouter", "ollama"):
            self.assertTrue(by_name[pid]["adapter_available"])

    def test_invalid_verifier_type_returns_422(self):
        """An unrecognized literal for verifier_type gets caught by Pydantic → 422."""
        payload = {
            "question": "q",
            "answer": "Some answer.",
            "sources": [{"text": "Some source."}],
            "config": {"verifier_type": "totally_fake"},
        }
        res = self.client.post("/api/evaluations", json=payload)
        self.assertEqual(res.status_code, 422)

    def test_llm_verifier_type_empty_model_id_returns_400(self):
        payload = {
            "question": "q",
            "answer": "Some answer.",
            "sources": [{"text": "Some source."}],
            "config": {"verifier_type": "llm", "provider_id": "gemini", "model_id": "   "},
        }
        res = self.client.post("/api/evaluations", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("model_id", res.json()["detail"])

    def test_llm_verifier_type_unimplemented_adapter_returns_400(self):
        payload = {
            "question": "q",
            "answer": "Some answer.",
            "sources": [{"text": "Some source."}],
            "config": {"verifier_type": "llm", "provider_id": "openai"},
        }
        res = self.client.post("/api/evaluations", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("adapter is not implemented yet", res.json()["detail"])

    def test_llm_verifier_type_evidence_based_verification_end_to_end(self):
        from unittest.mock import patch
        import os

        valid_verdict = _make_verdict(
            "C1", "SUPPORTED",
            supporting=[("S1", "The Eiffel Tower was completed in 1889.")],
            reasoning="Verbatim match found in source.",
            confidence=0.95,
        )
        fake_gemini_resp = {
            "candidates": [{"content": {"parts": [{"text": valid_verdict}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 15, "candidatesTokenCount": 10},
        }

        mock_client = _mock_client([(200, fake_gemini_resp)])

        old_key = os.environ.get("GEMINI_API_KEY")
        old_model = os.environ.get("GEMINI_MODEL")
        os.environ["GEMINI_API_KEY"] = "AIzaFAKEKEY00000000000000"
        os.environ["GEMINI_MODEL"] = "gemini-1.5-flash"
        try:
            with patch("app.providers.gemini.httpx.AsyncClient", return_value=mock_client):
                payload = {
                    "question": "When was it built?",
                    "answer": "The Eiffel Tower was completed in 1889.",
                    "sources": [{"id": "S1", "text": "The Eiffel Tower was completed in 1889."}],
                    "config": {"verifier_type": "llm", "provider_id": "gemini", "model_id": "gemini-1.5-flash"},
                }
                res = self.client.post("/api/evaluations", json=payload)
                self.assertEqual(res.status_code, 201)
                data = res.json()
                self.assertEqual(data["status"], "completed")
                self.assertEqual(len(data["verifications"]), 1)
                v = data["verifications"][0]
                self.assertEqual(v["classification"], "SUPPORTED")
                self.assertEqual(v["supporting"][0]["source_id"], "S1")
                self.assertEqual(v["supporting"][0]["excerpt"], "The Eiffel Tower was completed in 1889.")
                self.assertIn("llm:gemini:gemini-1.5-flash", v["method"])
        finally:
            if old_key is not None:
                os.environ["GEMINI_API_KEY"] = old_key
            else:
                os.environ.pop("GEMINI_API_KEY", None)
            if old_model is not None:
                os.environ["GEMINI_MODEL"] = old_model
            else:
                os.environ.pop("GEMINI_MODEL", None)


# ---------------------------------------------------------------------------
# Secret Redaction Tests for New Providers
# ---------------------------------------------------------------------------

class ProviderRedactionTests(unittest.TestCase):
    def test_gemini_key_pattern_is_redacted(self):
        from app.core.redaction import redact_secrets
        key = "AIzaSyD-FAKEKEYVALUE12345"
        redacted = redact_secrets(f"Authorization: {key}")
        self.assertNotIn(key, redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_gemini_url_query_key_is_redacted(self):
        from app.core.redaction import redact_secrets
        url1 = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=AIzaSyFakeKey1234567890"
        redacted1 = redact_secrets(url1)
        self.assertNotIn("AIzaSyFakeKey1234567890", redacted1)
        self.assertEqual(redacted1, "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=[REDACTED]")

        url2 = "https://example.com/api?foo=bar&key=some-custom-token-xyz&baz=1"
        redacted2 = redact_secrets(url2)
        self.assertNotIn("some-custom-token-xyz", redacted2)
        self.assertEqual(redacted2, "https://example.com/api?foo=bar&key=[REDACTED]&baz=1")

    def test_groq_key_pattern_is_redacted(self):
        from app.core.redaction import redact_secrets
        key = "gsk_FAKEKEY0000000000000000"
        redacted = redact_secrets(f"Bearer {key}")
        self.assertNotIn(key, redacted)

    def test_openrouter_key_pattern_is_redacted(self):
        from app.core.redaction import redact_secrets
        key = "sk-or-FAKEOPENROUTERKEY00000"
        redacted = redact_secrets(f"Bearer {key}")
        self.assertNotIn(key, redacted)

    def test_error_result_does_not_contain_raw_key(self):
        """Provider errors passed through generate_answer must have secrets stripped."""
        from app.providers.base import ProviderError
        from app.providers.mock import MockProvider
        secret = "sk-realSecretKey123456789"
        p = MockProvider(
            script=[ProviderError(ErrorCategory.AUTHENTICATION, f"bad key {secret}")],
            retry=RetryPolicy(max_attempts=1),
            sleep=_no_sleep,
        )
        r = run(p.generate_answer("hi"))
        self.assertFalse(r.ok)
        self.assertNotIn(secret, r.error_message or "")


if __name__ == "__main__":
    unittest.main()
