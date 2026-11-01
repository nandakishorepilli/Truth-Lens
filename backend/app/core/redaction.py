"""Secret redaction and key masking. Applied to logs, errors, and exports."""
from __future__ import annotations

import re
from typing import Any, Mapping

REDACTED = "[REDACTED]"

_SECRET_PATTERN = re.compile(
    r"sk-ant-[A-Za-z0-9_\-]{8,}"
    r"|sk-or-[A-Za-z0-9_\-]{8,}"
    r"|sk-[A-Za-z0-9_\-]{16,}"
    r"|AIza[0-9A-Za-z_\-]{20,}"
    r"|gsk_[A-Za-z0-9]{16,}"
    r"|xai-[A-Za-z0-9]{16,}"
    r"|Bearer\s+[A-Za-z0-9._\-]{8,}"
)
_SENSITIVE_HEADERS = {
    "authorization", "proxy-authorization", "x-api-key", "x-goog-api-key", "api-key",
}


def redact_secrets(text: str) -> str:
    return _SECRET_PATTERN.sub(REDACTED, text)


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {k: (REDACTED if k.lower() in _SENSITIVE_HEADERS else redact_secrets(v)) for k, v in headers.items()}


def redact_obj(value: Any) -> Any:
    """Recursively redact every string inside plain dict/list structures."""
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {k: redact_obj(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_obj(v) for v in value]
    return value


def mask_key(key: str | None) -> str | None:
    """Show only a short suffix of a configured key; short keys are fully hidden."""
    if not key:
        return None
    return "••••" if len(key) <= 8 else "••••" + key[-4:]
