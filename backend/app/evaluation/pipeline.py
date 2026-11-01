"""Evaluation pipeline: prepare -> extract -> verify -> aggregate."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Sequence

from app.core.redaction import redact_secrets
from app.evaluation.claims import ExtractionResult, extract_claims
from app.evaluation.metrics import Metrics, compute_metrics
from app.evaluation.models import (Claim, Source, Verification, VerificationStatus, prepare_input)
from app.evaluation.verify import Verifier

LIMITATIONS = (
    "Results show whether the SUPPLIED sources support each claim. They do not establish objective truth.",
    "Claim extraction and verification can both be wrong, especially LLM-based ones; review the excerpts.",
    "Different prompts or models for extraction and verification do not guarantee statistical independence.",
    "The rule-based baseline uses term overlap, numbers and negation. It is not a complete factuality detector.",
)


@dataclass(frozen=True)
class EvaluationConfig:
    extractor: str = "rule_based_sentence_splitter"
    verifier: str = "rule_based_baseline"
    max_concurrency: int = 4

    def as_dict(self) -> dict:
        return {"extractor": self.extractor, "verifier": self.verifier, "max_concurrency": self.max_concurrency}


@dataclass
class EvaluationReport:
    run_id: str
    created_at: str
    status: str  # completed | completed_with_errors | failed
    question: str
    answer: str
    sources: list[Source]
    claims: list[Claim]
    skipped: list
    verifications: list[Verification]
    metrics: Metrics
    config: dict
    stages: list[dict] = field(default_factory=list)
    limitations: tuple[str, ...] = LIMITATIONS


async def run_evaluation(question: str, answer: str, sources: list, *, verifier: Verifier,
                         config: EvaluationConfig | None = None,
                         on_stage: Callable[[str, str], None] | None = None,
                         extractor: Callable[[str], ExtractionResult] = extract_claims) -> EvaluationReport:
    """Raises InputError for invalid input. Verifier failures are recorded per claim."""
    cfg = config or EvaluationConfig(verifier=verifier.name)
    stages: list[dict] = []

    def mark(name: str, state: str) -> None:
        stages.append({"stage": name, "state": state})
        if on_stage:
            on_stage(name, state)

    mark("input_preparation", "started")
    prepared = prepare_input(question, answer, sources)
    mark("input_preparation", "done")

    mark("claim_extraction", "started")
    extraction = extractor(prepared.answer)
    mark("claim_extraction", "done")

    mark("evidence_verification", "started")
    sem = asyncio.Semaphore(max(1, cfg.max_concurrency))

    async def one(claim: Claim) -> Verification:
        async with sem:
            try:
                return await verifier.verify(claim, prepared.sources)
            except Exception as e:  # a crashing verifier must not look like "insufficient evidence"
                return Verification(claim.id, VerificationStatus.ERROR,
                                    error=redact_secrets(f"{type(e).__name__}: {e}"), method=verifier.name)

    verifications = list(await asyncio.gather(*(one(c) for c in extraction.claims)))
    mark("evidence_verification", "done")

    mark("aggregation", "started")
    metrics = compute_metrics(len(extraction.claims), verifications)
    mark("aggregation", "done")

    if metrics.errors == 0:
        status = "completed"
    elif metrics.errors == len(verifications):
        status = "failed"  # nothing was successfully verified
    else:
        status = "completed_with_errors"
    return EvaluationReport(uuid.uuid4().hex, datetime.now(timezone.utc).isoformat(), status, prepared.question,
                            prepared.answer, prepared.sources, extraction.claims, extraction.skipped,
                            verifications, metrics, cfg.as_dict(), stages)
