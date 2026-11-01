"""FastAPI route handlers for TruthLens API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import (
    EvaluationCreateRequest,
    HealthResponse,
    ProvidersResponse,
    VerifierConfigInput,
)
from app.core.config import provider_statuses
from app.db.repository import (
    get_evaluation_record,
    record_to_evaluation_report,
    save_evaluation_report,
)
from app.db.session import get_db
from app.evaluation.models import InputError
from app.evaluation.pipeline import EvaluationConfig, run_evaluation
from app.evaluation.verify import LLMVerifier, RuleBasedVerifier
from app.providers.mock import MockProvider
from app.reporting.export import report_to_csv, report_to_dict, report_to_json

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """System health check and database connectivity verification."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        version="0.1.0",
        database=db_status,
    )


@router.get("/providers", response_model=ProvidersResponse)
def list_providers() -> ProvidersResponse:
    """List provider integration statuses with masked key previews."""
    return ProvidersResponse(providers=provider_statuses())


@router.post("/evaluations", status_code=status.HTTP_201_CREATED)
async def create_evaluation(
    payload: EvaluationCreateRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Run an evaluation against supplied sources and persist the report."""
    cfg = payload.config or VerifierConfigInput()

    if cfg.verifier_type == "rule_based":
        verifier = RuleBasedVerifier()
    elif cfg.verifier_type == "mock":
        provider = MockProvider(script=cfg.mock_responses or ["{}"])
        verifier = LLMVerifier(provider=provider)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported verifier type '{cfg.verifier_type}'. Supported: 'rule_based', 'mock'.",
        )

    eval_cfg = EvaluationConfig(
        verifier=verifier.name,
        max_concurrency=cfg.max_concurrency,
    )

    sources = [s.model_dump() for s in payload.sources]

    try:
        report = await run_evaluation(
            question=payload.question,
            answer=payload.answer,
            sources=sources,
            verifier=verifier,
            config=eval_cfg,
        )
    except InputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Evaluation processing failed.",
        )

    try:
        save_evaluation_report(db, report)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist evaluation report.",
        )

    return report_to_dict(report)


@router.get("/evaluations/{run_id}")
def get_evaluation(run_id: str, db: Session = Depends(get_db)) -> dict:
    """Retrieve an evaluation report by run_id."""
    record = get_evaluation_record(db, run_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation '{run_id}' not found.",
        )
    report = record_to_evaluation_report(record)
    return report_to_dict(report)


@router.get("/evaluations/{run_id}/export")
def export_evaluation(
    run_id: str,
    format: str = Query(..., description="Export format: 'json' or 'csv'"),
    db: Session = Depends(get_db),
) -> Response:
    """Export an evaluation report in JSON or CSV format."""
    record = get_evaluation_record(db, run_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation '{run_id}' not found.",
        )

    fmt = format.lower().strip()
    report = record_to_evaluation_report(record)

    if fmt == "csv":
        csv_text = report_to_csv(report)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="truthlens-{run_id}.csv"'},
        )
    elif fmt == "json":
        json_text = report_to_json(report)
        return Response(
            content=json_text,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="truthlens-{run_id}.json"'},
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported export format '{format}'. Supported formats: 'json', 'csv'.",
        )
