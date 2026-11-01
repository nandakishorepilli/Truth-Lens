"""Aggregate metrics. Every ratio carries its numerator and denominator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.evaluation.models import Classification, Verification, VerificationStatus


@dataclass(frozen=True)
class Ratio:
    numerator: int
    denominator: int
    value: float | None  # None when the denominator is zero (undefined, not 0%)


def ratio(n: int, d: int) -> Ratio:
    return Ratio(n, d, (n / d) if d else None)


@dataclass(frozen=True)
class Metrics:
    total_claims: int
    supported: int
    contradicted: int
    insufficient_evidence: int
    errors: int
    conflicts: int
    supported_claim_rate: Ratio
    evidence_coverage: Ratio
    verification_completion_rate: Ratio


METRIC_DEFINITIONS = {
    "supported_claim_rate": "supported_claims / successfully_classified_claims. The share of classified claims "
                            "the supplied evidence supports. It is NOT the probability that the answer is true.",
    "evidence_coverage": "claims_with_relevant_evidence / factual_claims. A claim has relevant evidence when "
                         "at least one supporting or contradicting excerpt was found. Errors count in the denominator.",
    "verification_completion_rate": "successfully_classified_claims / factual_claims. Claims whose verification "
                                    "errored (timeout, malformed output, provider failure) lower this rate.",
    "errors": "Verification failures. Reported separately; never merged into insufficient_evidence.",
    "conflicts": "Classified claims where sources disagree. They are counted as insufficient_evidence.",
}


def compute_metrics(total_claims: int, verifications: Sequence[Verification]) -> Metrics:
    classified = [v for v in verifications if v.status == VerificationStatus.CLASSIFIED]
    count = lambda c: sum(1 for v in classified if v.classification == c)  # noqa: E731
    supported = count(Classification.SUPPORTED)
    with_evidence = sum(1 for v in classified if v.supporting or v.contradicting)
    return Metrics(
        total_claims=total_claims,
        supported=supported,
        contradicted=count(Classification.CONTRADICTED),
        insufficient_evidence=count(Classification.INSUFFICIENT_EVIDENCE),
        errors=sum(1 for v in verifications if v.status == VerificationStatus.ERROR),
        conflicts=sum(1 for v in classified if v.conflict),
        supported_claim_rate=ratio(supported, len(classified)),
        evidence_coverage=ratio(with_evidence, total_claims),
        verification_completion_rate=ratio(len(classified), total_claims),
    )
