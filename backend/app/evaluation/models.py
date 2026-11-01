"""Domain types and input preparation. Framework-free so they are testable anywhere."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from app.evaluation.text_utils import normalize_text

MAX_QUESTION_CHARS = 2_000
MAX_ANSWER_CHARS = 20_000
MAX_SOURCE_CHARS = 200_000
MAX_SOURCES = 20


class InputError(ValueError):
    """Invalid user input. Safe to show to the user."""


class Classification(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class VerificationStatus(str, Enum):
    CLASSIFIED = "CLASSIFIED"
    ERROR = "ERROR"  # verification failed; this is NOT the same as insufficient evidence


@dataclass(frozen=True)
class Source:
    id: str
    text: str
    title: str | None = None
    url: str | None = None  # stored for display only; never fetched


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    position: int  # character offset in the normalized answer


@dataclass(frozen=True)
class Evidence:
    source_id: str
    excerpt: str  # always a verbatim slice: source.text[start:end] == excerpt
    start: int
    end: int


@dataclass
class Verification:
    claim_id: str
    status: VerificationStatus
    classification: Classification | None = None
    supporting: list[Evidence] = field(default_factory=list)
    contradicting: list[Evidence] = field(default_factory=list)
    reasoning: str = ""
    confidence: float | None = None  # None unless the method yields a defensible score
    conflict: bool = False  # sources disagree; both sides are exposed
    error: str | None = None
    method: str = ""


@dataclass(frozen=True)
class PreparedInput:
    question: str
    answer: str
    sources: list[Source]


_URL = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)


def prepare_input(question: str, answer: str, sources: list) -> PreparedInput:
    """Normalize and validate. Sources may be Source objects or dicts (text/title/url/id)."""
    q, a = normalize_text(question or ""), normalize_text(answer or "")
    if not q:
        raise InputError("Question is required.")
    if not a:
        raise InputError("Answer is required.")
    if len(q) > MAX_QUESTION_CHARS:
        raise InputError(f"Question exceeds {MAX_QUESTION_CHARS} characters.")
    if len(a) > MAX_ANSWER_CHARS:
        raise InputError(f"Answer exceeds {MAX_ANSWER_CHARS} characters.")
    if not sources:
        raise InputError("At least one source document is required.")
    if len(sources) > MAX_SOURCES:
        raise InputError(f"At most {MAX_SOURCES} sources are allowed.")
    prepared: list[Source] = []
    seen: set[str] = set()
    for i, s in enumerate(sources, start=1):
        d = s if isinstance(s, dict) else {"id": s.id, "text": s.text, "title": s.title, "url": s.url}
        text = normalize_text(d.get("text") or "")
        if not text:
            raise InputError(f"Source {i} is empty.")
        if len(text) > MAX_SOURCE_CHARS:
            raise InputError(f"Source {i} exceeds {MAX_SOURCE_CHARS} characters.")
        sid = (d.get("id") or f"S{i}").strip()
        if sid in seen:
            raise InputError(f"Duplicate source id: {sid}")
        seen.add(sid)
        url = (d.get("url") or "").strip() or None
        if url and not _URL.match(url):
            raise InputError(f"Source {sid} has an invalid URL; only http(s) URLs are accepted.")
        prepared.append(Source(sid, text, (d.get("title") or "").strip() or None, url))
    return PreparedInput(q, a, prepared)
