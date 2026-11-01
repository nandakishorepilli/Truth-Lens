"""Provider-independent contract: timeouts, bounded retries, normalized results."""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable

from app.core.redaction import redact_secrets


class ErrorCategory(str, Enum):
    NOT_CONFIGURED = "not_configured"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    PROVIDER_OUTAGE = "provider_outage"
    BAD_REQUEST = "bad_request"
    MALFORMED_RESPONSE = "malformed_response"
    UNKNOWN = "unknown"


# Authentication, configuration and bad-request errors are never retried.
RETRYABLE = frozenset({ErrorCategory.RATE_LIMIT, ErrorCategory.TIMEOUT, ErrorCategory.PROVIDER_OUTAGE})


class ProviderError(Exception):
    def __init__(self, category: ErrorCategory, message: str, *, retry_after: float | None = None,
                 status_code: int | None = None):
        super().__init__(message)
        self.category = category
        self.retry_after = retry_after
        self.status_code = status_code


def classify_http_status(status: int) -> ErrorCategory:
    if status in (401, 403):
        return ErrorCategory.AUTHENTICATION
    if status == 429:
        return ErrorCategory.RATE_LIMIT
    if status == 408:
        return ErrorCategory.TIMEOUT
    if status >= 500:
        return ErrorCategory.PROVIDER_OUTAGE
    if 400 <= status < 500:
        return ErrorCategory.BAD_REQUEST
    return ErrorCategory.UNKNOWN


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_s: float = 0.5
    max_delay_s: float = 8.0

    def delay(self, attempt: int, retry_after: float | None = None) -> float:
        d = min(self.max_delay_s, self.base_delay_s * (2 ** (attempt - 1)))
        if retry_after is not None:
            d = min(self.max_delay_s, max(d, retry_after))
        return d


@dataclass(frozen=True)
class RawCompletion:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    model: str | None
    status: str  # "ok" | "error"
    text: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: float
    estimated_cost_usd: float | None
    error_category: ErrorCategory | None
    error_message: str | None
    attempts: int

    @property
    def ok(self) -> bool:
        return self.status == "ok"


@dataclass(frozen=True)
class ConnectionStatus:
    provider: str
    ok: bool
    category: ErrorCategory | None
    detail: str


class Provider(ABC):
    """Adapters implement only `_complete`; everything else is shared and tested once.

    A provider never falls back to another provider by itself. Any fallback must be
    chosen and recorded by the caller.
    """

    name = "provider"

    def __init__(self, model: str | None, *, retry: RetryPolicy | None = None,
                 sleep: Callable[[float], Awaitable[None]] | None = None,
                 pricing_per_mtok: tuple[float, float] | None = None):
        self.model = model
        self.retry = retry or RetryPolicy()
        self._sleep = sleep or asyncio.sleep
        self._pricing = pricing_per_mtok  # (input $/1M tokens, output $/1M tokens), from config only

    @abstractmethod
    async def _complete(self, prompt: str, system: str | None) -> RawCompletion: ...

    async def generate_answer(self, prompt: str, *, system: str | None = None,
                              timeout_s: float = 30.0) -> ProviderResult:
        started = time.perf_counter()
        attempts = 0
        while True:
            attempts += 1
            try:
                raw = await asyncio.wait_for(self._complete(prompt, system), timeout_s)
                return ProviderResult(
                    self.name, self.model, "ok", raw.text, raw.input_tokens, raw.output_tokens,
                    (time.perf_counter() - started) * 1000,
                    self.estimate_cost(raw.input_tokens, raw.output_tokens), None, None, attempts)
            except asyncio.TimeoutError:
                err = ProviderError(ErrorCategory.TIMEOUT, f"request exceeded {timeout_s}s")
            except ProviderError as e:
                err = e
            except Exception as e:  # adapter bug or transport failure; never leak the message
                err = ProviderError(ErrorCategory.UNKNOWN, type(e).__name__)
            if err.category not in RETRYABLE or attempts >= self.retry.max_attempts:
                return ProviderResult(
                    self.name, self.model, "error", "", None, None,
                    (time.perf_counter() - started) * 1000, None, err.category,
                    redact_secrets(str(err)), attempts)
            await self._sleep(self.retry.delay(attempts, err.retry_after))

    async def check_connection(self) -> ConnectionStatus:
        r = await self.generate_answer("Reply with the word OK.", timeout_s=10.0)
        return ConnectionStatus(self.name, r.ok, r.error_category, r.error_message or "connection ok")

    def get_model_metadata(self) -> dict:
        return {"provider": self.name, "model": self.model, "pricing_configured": self._pricing is not None}

    def estimate_cost(self, input_tokens: int | None, output_tokens: int | None) -> float | None:
        """None unless pricing was configured AND the provider reported token counts."""
        if self._pricing is None or input_tokens is None or output_tokens is None:
            return None
        return (input_tokens * self._pricing[0] + output_tokens * self._pricing[1]) / 1_000_000

    @staticmethod
    def get_usage_metadata(result: ProviderResult) -> dict:
        return {"input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
                "latency_ms": round(result.latency_ms, 2), "estimated_cost_usd": result.estimated_cost_usd}
