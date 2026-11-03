"""Ollama provider adapter.

Uses the local Ollama REST API.
Default endpoint: http://localhost:11434/api/generate
Authentication: none (Ollama is keyless by design for local use)

Ollama must be running locally with the desired model already pulled:
  ollama pull llama3.1
  ollama pull mistral

If the Ollama server is not running, the adapter raises PROVIDER_OUTAGE
with a clear message — it does NOT silently fall back to another provider.

Configure via OLLAMA_BASE_URL (default http://localhost:11434) and
OLLAMA_MODEL environment variables.
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

OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider(Provider):
    """Adapter for a locally-running Ollama server."""

    name = "ollama"

    def __init__(
        self,
        model: str,
        *,
        base_url: str = OLLAMA_DEFAULT_BASE_URL,
        retry: RetryPolicy | None = None,
        pricing_per_mtok: tuple[float, float] | None = None,
        http_client: httpx.AsyncClient | None = None,
        **kw,
    ) -> None:
        super().__init__(model, retry=retry, pricing_per_mtok=pricing_per_mtok, **kw)
        if not model:
            raise ValueError("OllamaProvider requires a non-empty model")
        self._base_url = (base_url or OLLAMA_DEFAULT_BASE_URL).rstrip("/")
        self._http_client = http_client

    def _build_payload(self, prompt: str, system: str | None) -> dict:
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,  # always request a single complete response
        }
        if system:
            payload["system"] = system
        return payload

    async def _complete(self, prompt: str, system: str | None) -> RawCompletion:
        url = f"{self._base_url}/api/generate"
        payload = self._build_payload(prompt, system)

        try:
            client = self._http_client
            if client is None:
                async with httpx.AsyncClient(timeout=120.0) as c:
                    response = await c.post(url, json=payload)
            else:
                response = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderError(ErrorCategory.TIMEOUT, "Ollama request timed out") from exc
        except httpx.ConnectError as exc:
            # Ollama not running is reported as PROVIDER_OUTAGE, not UNKNOWN
            raise ProviderError(
                ErrorCategory.PROVIDER_OUTAGE,
                f"Cannot connect to Ollama at {self._base_url}. "
                "Is the Ollama server running? Start it with: ollama serve",
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(ErrorCategory.UNKNOWN, type(exc).__name__) from exc

        if response.status_code != 200:
            category = classify_http_status(response.status_code)
            try:
                body = response.json()
                msg = body.get("error", response.text[:200])
            except Exception:
                msg = response.text[:200]
            clean_msg = redact_secrets(str(msg))
            raise ProviderError(category, f"Ollama HTTP {response.status_code}: {clean_msg}",
                                status_code=response.status_code)

        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise ProviderError(ErrorCategory.MALFORMED_RESPONSE,
                                "Ollama response is not valid JSON") from exc

        # Ollama generate response: {"response": "...", "done": true, ...}
        text = body.get("response")
        if not isinstance(text, str) or not text.strip():
            raise ProviderError(ErrorCategory.MALFORMED_RESPONSE,
                                "Ollama returned an empty or missing 'response' field")

        # Token counts: prompt_eval_count and eval_count
        input_tokens: int | None = body.get("prompt_eval_count")
        output_tokens: int | None = body.get("eval_count")

        return RawCompletion(
            text=text,
            input_tokens=int(input_tokens) if input_tokens is not None else None,
            output_tokens=int(output_tokens) if output_tokens is not None else None,
        )
