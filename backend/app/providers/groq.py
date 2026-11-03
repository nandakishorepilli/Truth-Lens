"""Groq provider adapter.

Uses the Groq OpenAI-compatible chat completions API.
Endpoint: https://api.groq.com/openai/v1/chat/completions
Authentication: Authorization: Bearer <api_key>

Supported models: llama-3.1-8b-instant, llama-3.3-70b-versatile,
                  mixtral-8x7b-32768, gemma2-9b-it, etc.
Configure via GROQ_API_KEY and GROQ_MODEL environment variables.
"""
from __future__ import annotations

import json

import httpx

from app.core.redaction import redact_secrets
from app.providers.base import (
    ErrorCategory,
    Provider,
    ProviderError,
    RawCompletion,
    RetryPolicy,
    classify_http_status,
)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(Provider):
    """Adapter for the Groq LLM inference API (OpenAI-compatible)."""

    name = "groq"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = GROQ_BASE_URL,
        retry: RetryPolicy | None = None,
        pricing_per_mtok: tuple[float, float] | None = None,
        http_client: httpx.AsyncClient | None = None,
        **kw,
    ) -> None:
        super().__init__(model, retry=retry, pricing_per_mtok=pricing_per_mtok, **kw)
        if not api_key:
            raise ValueError("GroqProvider requires a non-empty api_key")
        if not model:
            raise ValueError("GroqProvider requires a non-empty model")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._http_client = http_client

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, prompt: str, system: str | None) -> dict:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return {"model": self.model, "messages": messages}

    async def _complete(self, prompt: str, system: str | None) -> RawCompletion:
        url = f"{self._base_url}/chat/completions"
        headers = self._headers()
        payload = self._build_payload(prompt, system)

        try:
            client = self._http_client
            if client is None:
                async with httpx.AsyncClient(timeout=60.0) as c:
                    response = await c.post(url, headers=headers, json=payload)
            else:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderError(ErrorCategory.TIMEOUT, "Groq request timed out") from exc
        except httpx.ConnectError as exc:
            raise ProviderError(ErrorCategory.PROVIDER_OUTAGE, "Groq connection failed") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(ErrorCategory.UNKNOWN, type(exc).__name__) from exc

        if response.status_code != 200:
            category = classify_http_status(response.status_code)
            try:
                body = response.json()
                msg = body.get("error", {}).get("message", response.text[:200])
            except Exception:
                msg = response.text[:200]
            retry_after: float | None = None
            if response.status_code == 429:
                try:
                    retry_after = float(response.headers.get("Retry-After", 0)) or None
                except (ValueError, TypeError):
                    pass
            clean_msg = redact_secrets(str(msg))
            raise ProviderError(category, f"Groq HTTP {response.status_code}: {clean_msg}",
                                retry_after=retry_after, status_code=response.status_code)

        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise ProviderError(ErrorCategory.MALFORMED_RESPONSE,
                                "Groq response is not valid JSON") from exc

        # OpenAI-compatible response: choices[0].message.content
        try:
            text: str = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(ErrorCategory.MALFORMED_RESPONSE,
                                f"Unexpected Groq response structure: {type(exc).__name__}") from exc

        if not isinstance(text, str) or not text.strip():
            raise ProviderError(ErrorCategory.MALFORMED_RESPONSE, "Groq returned an empty response")

        # Token usage
        usage = body.get("usage", {})
        input_tokens: int | None = usage.get("prompt_tokens")
        output_tokens: int | None = usage.get("completion_tokens")

        return RawCompletion(
            text=text,
            input_tokens=int(input_tokens) if input_tokens is not None else None,
            output_tokens=int(output_tokens) if output_tokens is not None else None,
        )
