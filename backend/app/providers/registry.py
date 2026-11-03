"""Central provider registry.

Instantiates and manages real provider adapters from environment configuration.
The registry is stateless (rebuilt from env on each request) to stay aligned
with the existing provider_statuses() pattern in core/config.py.

Usage:
    from app.providers.registry import ProviderRegistry
    registry = ProviderRegistry.from_env()
    provider = registry.get("gemini")   # Provider or UnconfiguredProvider
"""
from __future__ import annotations

import os
from typing import Mapping

from app.core.config import PROVIDER_SPECS, ProviderSpec
from app.providers.base import Provider
from app.providers.gemini import GeminiProvider
from app.providers.groq import GroqProvider
from app.providers.mock import UnconfiguredProvider
from app.providers.ollama import OllamaProvider
from app.providers.openrouter import OpenRouterProvider

# Provider IDs that have real adapter implementations in this milestone.
IMPLEMENTED_PROVIDER_IDS: frozenset[str] = frozenset({"gemini", "groq", "openrouter", "ollama"})


def _build_provider(spec: ProviderSpec, env: Mapping[str, str]) -> Provider:
    """Instantiate the correct adapter for spec, or return UnconfiguredProvider."""
    name = spec.name

    if name == "gemini":
        key = env.get(spec.key_env or "", "")
        model = env.get(spec.model_env, "")
        if not key or not model:
            return UnconfiguredProvider(name)
        return GeminiProvider(api_key=key, model=model)

    if name == "groq":
        key = env.get(spec.key_env or "", "")
        model = env.get(spec.model_env, "")
        if not key or not model:
            return UnconfiguredProvider(name)
        return GroqProvider(api_key=key, model=model)

    if name == "openrouter":
        key = env.get(spec.key_env or "", "")
        model = env.get(spec.model_env, "")
        if not key or not model:
            return UnconfiguredProvider(name)
        return OpenRouterProvider(api_key=key, model=model)

    if name == "ollama":
        model = env.get(spec.model_env, "")
        base_url = env.get(spec.base_url_env or "", "") or "http://localhost:11434"
        if not model:
            return UnconfiguredProvider(name)
        return OllamaProvider(model=model, base_url=base_url)

    # Provider exists in PROVIDER_SPECS but has no adapter in this milestone.
    return UnconfiguredProvider(name)


class ProviderRegistry:
    """Maps provider IDs to instantiated (or unconfigured) Provider adapters."""

    def __init__(self, providers: dict[str, Provider]) -> None:
        self._providers = providers

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ProviderRegistry":
        """Build a registry from the current process environment (or a supplied mapping)."""
        e = os.environ if env is None else env
        return cls({spec.name: _build_provider(spec, e) for spec in PROVIDER_SPECS})

    def get(self, provider_id: str) -> Provider:
        """Return the provider adapter.  Unknown IDs get an UnconfiguredProvider."""
        return self._providers.get(provider_id, UnconfiguredProvider(provider_id))

    def is_configured(self, provider_id: str) -> bool:
        """True only if the provider has a real adapter AND its credentials are present."""
        p = self._providers.get(provider_id)
        return p is not None and not isinstance(p, UnconfiguredProvider)

    def implemented_ids(self) -> frozenset[str]:
        return IMPLEMENTED_PROVIDER_IDS

    def all_providers(self) -> dict[str, Provider]:
        return dict(self._providers)
