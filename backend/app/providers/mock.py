"""Deterministic providers for tests and offline development. Never used for live results."""
from __future__ import annotations

import asyncio
from typing import Callable

from app.providers.base import ErrorCategory, Provider, ProviderError, RawCompletion


class Hang:
    """Script item that never completes, to exercise timeout handling."""


class MockProvider(Provider):
    name = "mock"

    def __init__(self, script: list | None = None, responder: Callable[[str], str] | None = None, **kw):
        super().__init__(kw.pop("model", "mock-model"), **kw)
        self.script = list(script or [])
        self.responder = responder
        self.calls: list[str] = []

    async def _complete(self, prompt: str, system: str | None) -> RawCompletion:
        self.calls.append(prompt)
        if self.script:
            item = self.script.pop(0)
        elif self.responder:
            item = self.responder(prompt)
        else:
            raise AssertionError("MockProvider script exhausted")
        if isinstance(item, Hang):
            await asyncio.sleep(3600)
        if isinstance(item, ProviderError):
            raise item
        if isinstance(item, RawCompletion):
            return item
        return RawCompletion(str(item), input_tokens=len(prompt.split()), output_tokens=len(str(item).split()))


class UnconfiguredProvider(Provider):
    """Placeholder for a provider with no credentials: fails fast with a clear category."""

    def __init__(self, name: str):
        super().__init__(None)
        self.name = name

    async def _complete(self, prompt: str, system: str | None) -> RawCompletion:
        raise ProviderError(ErrorCategory.NOT_CONFIGURED, f"{self.name} is not configured")
