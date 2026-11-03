"""CRUD repository for evaluation records."""
from __future__ import annotations

from dataclasses import asdict
from sqlalchemy.orm import Session

from app.db.models import ClaimRecord, EvaluationRecord, VerificationRecord
from app.evaluation.claims import SkippedSegment
from app.evaluation.metrics import Metrics, Ratio
from app.evaluation.models import (
    Claim,
    Classification,
    Evidence,
    Source,
    Verification,
    VerificationStatus,
)
from app.evaluation.pipeline import EvaluationReport
from app.reporting.export import report_to_dict


def save_evaluation_report(db: Session, report: EvaluationReport) -> EvaluationRecord:
    """Save an EvaluationReport and associated claims and verifications to the database."""
    report_dict = report_to_dict(report)

    claims = [
        ClaimRecord(
            claim_id=c.id,
            text=c.text,
            position=c.position,
        )
        for c in report.claims
    ]

    verifications = [
        VerificationRecord(
            claim_id=v.claim_id,
            status=v.status.value,
            classification=v.classification.value if v.classification else None,
            confidence=v.confidence,
            conflict=v.conflict,
            reasoning=v.reasoning,
            error=v.error,
            method=v.method,
            supporting_data=[asdict(e) for e in v.supporting],
            contradicting_data=[asdict(e) for e in v.contradicting],
        )
        for v in report.verifications
    ]

    record = EvaluationRecord(
        run_id=report.run_id,
        created_at=report.created_at,
        status=report.status,
        question=report.question,
        answer=report.answer,
        sources_data=[asdict(s) for s in report.sources],
        skipped_data=[asdict(s) for s in report.skipped],
        metrics_data=report_dict.get("metrics", {}),
        config_data=report.config,
        stages_data=report.stages,
        limitations_data=list(report.limitations),
        raw_report=report_dict,
        claims=claims,
        verifications=verifications,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_evaluation_record(db: Session, run_id: str) -> EvaluationRecord | None:
    """Fetch an evaluation record by its unique run_id."""
    return db.query(EvaluationRecord).filter(EvaluationRecord.run_id == run_id).first()


def list_evaluation_records(
    db: Session,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[EvaluationRecord], int]:
    """Return a page of evaluation records (newest first) and the total count."""
    total: int = db.query(EvaluationRecord).count()
    records = (
        db.query(EvaluationRecord)
        .order_by(EvaluationRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return records, total


def record_to_evaluation_report(record: EvaluationRecord) -> EvaluationReport:
    """Reconstruct an EvaluationReport domain dataclass from an EvaluationRecord."""
    sources = [
        Source(
            id=s["id"],
            text=s["text"],
            title=s.get("title"),
            url=s.get("url"),
        )
        for s in record.sources_data
    ]

    claims = [
        Claim(
            id=c.claim_id,
            text=c.text,
            position=c.position,
        )
        for c in record.claims
    ]

    skipped = [
        SkippedSegment(
            text=s["text"],
            position=s["position"],
            reason=s["reason"],
        )
        for s in record.skipped_data
    ]

    verifications = [
        Verification(
            claim_id=v.claim_id,
            status=VerificationStatus(v.status),
            classification=Classification(v.classification) if v.classification else None,
            supporting=[
                Evidence(
                    source_id=e["source_id"],
                    excerpt=e["excerpt"],
                    start=e["start"],
                    end=e["end"],
                )
                for e in v.supporting_data
            ],
            contradicting=[
                Evidence(
                    source_id=e["source_id"],
                    excerpt=e["excerpt"],
                    start=e["start"],
                    end=e["end"],
                )
                for e in v.contradicting_data
            ],
            reasoning=v.reasoning,
            confidence=v.confidence,
            conflict=v.conflict,
            error=v.error,
            method=v.method,
        )
        for v in record.verifications
    ]

    m = record.metrics_data
    metrics = Metrics(
        total_claims=m["total_claims"],
        supported=m["supported"],
        contradicted=m["contradicted"],
        insufficient_evidence=m["insufficient_evidence"],
        errors=m["errors"],
        conflicts=m["conflicts"],
        supported_claim_rate=Ratio(**m["supported_claim_rate"]),
        evidence_coverage=Ratio(**m["evidence_coverage"]),
        verification_completion_rate=Ratio(**m["verification_completion_rate"]),
    )

    return EvaluationReport(
        run_id=record.run_id,
        created_at=record.created_at,
        status=record.status,
        question=record.question,
        answer=record.answer,
        sources=sources,
        claims=claims,
        skipped=skipped,
        verifications=verifications,
        metrics=metrics,
        config=record.config_data,
        stages=record.stages_data,
        limitations=tuple(record.limitations_data),
    )
