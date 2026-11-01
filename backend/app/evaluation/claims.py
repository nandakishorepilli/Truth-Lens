"""Rule-based claim extraction (baseline).

Splits an answer into sentence-level claims and records why anything was skipped.
It does NOT split compound sentences into atomic claims, resolve pronouns, or judge
truth. An LLM extractor can replace it behind the same `extract_claims` signature.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.evaluation.models import Claim
from app.evaluation.text_utils import iter_segments

_IMPERATIVE = ("please ", "consider ", "remember ", "try ", "make sure ", "let's ", "let us ",
               "don't ", "do not ", "use ", "note that ", "feel free", "check ", "ensure ")
_OPINION = ("i think", "i believe", "i feel", "in my opinion", "in my view", "personally,")
_FILLER = ("sure", "certainly", "of course", "here is", "here's", "here are", "hope this helps", "let me know")


@dataclass(frozen=True)
class SkippedSegment:
    text: str
    position: int
    reason: str


@dataclass(frozen=True)
class ExtractionResult:
    claims: list[Claim]
    skipped: list[SkippedSegment]


def _skip_reason(text: str) -> str | None:
    low = text.lower()
    if text.endswith("?"):
        return "Question, not a factual claim."
    if text.endswith(":"):
        return "Introductory text, not a factual claim."
    if len(text.split()) < 3:
        return "Too short to verify."
    if low.startswith(_FILLER):
        return "Conversational filler."
    if low.startswith(_IMPERATIVE):
        return "Instruction, not a factual claim."
    if low.startswith(_OPINION):
        return "Opinion, not a verifiable claim."
    return None


def extract_claims(answer: str) -> ExtractionResult:
    claims: list[Claim] = []
    skipped: list[SkippedSegment] = []
    for start, end in iter_segments(answer):
        text = answer[start:end]
        reason = _skip_reason(text)
        if reason:
            skipped.append(SkippedSegment(text, start, reason))
        else:
            claims.append(Claim(f"C{len(claims) + 1}", text, start))
    return ExtractionResult(claims, skipped)
