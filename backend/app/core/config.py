"""Environment-driven configuration. No secret is ever returned in plaintext."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from app.core.redaction import mask_key


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    key_env: str | None  # None for keyless local endpoints
    model_env: str
    base_url_env: str | None = None


# Model IDs are deliberately NOT defaulted: they must come from configuration.
PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec("gemini", "GEMINI_API_KEY", "GEMINI_MODEL"),
    ProviderSpec("groq", "GROQ_API_KEY", "GROQ_MODEL"),
    ProviderSpec("openrouter", "OPENROUTER_API_KEY", "OPENROUTER_MODEL"),
    ProviderSpec("openai", "OPENAI_API_KEY", "OPENAI_MODEL"),
    ProviderSpec("anthropic", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"),
    ProviderSpec("xai", "XAI_API_KEY", "XAI_MODEL"),
    ProviderSpec("ollama", None, "OLLAMA_MODEL", base_url_env="OLLAMA_BASE_URL"),
)

# Milestone 3A: real HTTP adapters for these four providers are implemented.
IMPLEMENTED_ADAPTERS: frozenset[str] = frozenset({"gemini", "groq", "openrouter", "ollama"})


def load_env_file(path: str | Path, env: dict[str, str] | None = None) -> None:
    """Minimal .env loader. Never overrides variables that are already set."""
    target = os.environ if env is None else env
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        target.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def parse_origins(value: str | None) -> list[str]:
    """Explicit CORS origins only; a wildcard is rejected."""
    origins = [o.strip() for o in (value or "").split(",") if o.strip()]
    if "*" in origins:
        raise ValueError("Wildcard CORS origins are not allowed; list explicit origins.")
    return origins


def provider_statuses(env: Mapping[str, str] | None = None) -> list[dict]:
    """Status per provider. Raw keys never leave this function."""
    env = os.environ if env is None else env
    out = []
    for spec in PROVIDER_SPECS:
        key = env.get(spec.key_env, "") if spec.key_env else None
        base = env.get(spec.base_url_env, "") if spec.base_url_env else None
        configured = bool(key) if spec.key_env else bool(base)
        out.append({
            "provider": spec.name,
            "configured": configured,
            "key_preview": mask_key(key),
            "model": env.get(spec.model_env) or None,
            "adapter_available": spec.name in IMPLEMENTED_ADAPTERS,
            "setup_hint": (f"Set {spec.key_env} and {spec.model_env} in backend/.env"
                           if spec.key_env else f"Set {spec.base_url_env} and {spec.model_env} in backend/.env"),
        })
    return out
