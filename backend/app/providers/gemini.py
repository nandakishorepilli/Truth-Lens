"""Google Gemini provider adapter.

Uses the Gemini REST API (v1beta generateContent endpoint).
Authentication is via ?key=<api_key> query parameter — NOT an Authorization header,
which is the Gemini-specific pattern distinct from OpenAI-compatible APIs.

Supported models: gemini-1.5-flash, gemini-1.5-pro, gemini-2.0-flash, etc.
Configure via GEMINI_API_KEY and GEMINI_MODEL environment variables.
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

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(Provider):
    """Adapter for the Google Gemini generative language API."""

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = GEMINI_BASE_URL,
        retry: RetryPolicy | None = None,
        pricing_per_mtok: tuple[float, float] | None = None,
        http_client: httpx.AsyncClient | None = None,
        **kw,
    ) -> None:
        super().__init__(model, retry=retry, pricing_per_mtok=pricing_per_mtok, **kw)
        if not api_key:
            raise ValueError("GeminiProvider requires a non-empty api_key")
        if not model:
            raise ValueError("GeminiProvider requires a non-empty model")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._http_client = http_client  # injected for tests; None → create per-request

    def _build_url(self) -> str:
        return f"{self._base_url}/models/{self.model}:generateContent"

    def _build_payload(self, prompt: str, system: str | None) -> dict:
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        payload: dict = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        return payload

    async def _complete(self, prompt: str, system: str | None) -> RawCompletion:
        url = self._build_url()
        params = {"key": self._api_key}
        payload = self._build_payload(prompt, system)

        try:
            client = self._http_client
            if client is None:
                async with httpx.AsyncClient(timeout=60.0) as c:
                    response = await c.post(url, params=params, json=payload)
            else:
                response = await client.post(url, params=params, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderError(ErrorCategory.TIMEOUT, "Gemini request timed out") from exc
        except httpx.ConnectError as exc:
            raise ProviderError(ErrorCategory.PROVIDER_OUTAGE, "Gemini connection failed") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(ErrorCategory.UNKNOWN, type(exc).__name__) from exc

        if response.status_code != 200:
            category = classify_http_status(response.status_code)
            # Extract error detail from Gemini's JSON error body when available
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
            raise ProviderError(category, f"Gemini HTTP {response.status_code}: {clean_msg}",
                                retry_after=retry_after, status_code=response.status_code)

        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise ProviderError(ErrorCategory.MALFORMED_RESPONSE,
                                "Gemini response is not valid JSON") from exc

        # Extract text from candidates[0].content.parts[0].text
        try:
            text: str = body["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            # Check for prompt blocks / safety stops
            finish_reason = ""
            try:
                finish_reason = body["candidates"][0].get("finishReason", "")
            except Exception:
                pass
            if finish_reason in ("SAFETY", "RECITATION", "BLOCKLIST"):
                raise ProviderError(ErrorCategory.BAD_REQUEST,
                                    f"Gemini blocked the response: finishReason={finish_reason}") from exc
            raise ProviderError(ErrorCategory.MALFORMED_RESPONSE,
                                f"Unexpected Gemini response structure: {type(exc).__name__}") from exc

        if not isinstance(text, str) or not text.strip():
            raise ProviderError(ErrorCategory.MALFORMED_RESPONSE, "Gemini returned an empty response")

        # Token usage (usageMetadata)
        usage = body.get("usageMetadata", {})
        input_tokens: int | None = usage.get("promptTokenCount")
        output_tokens: int | None = usage.get("candidatesTokenCount")

        return RawCompletion(
            text=text,
            input_tokens=int(input_tokens) if input_tokens is not None else None,
            output_tokens=int(output_tokens) if output_tokens is not None else None,
        )
