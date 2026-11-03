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
from app.core.config import PROVIDER_SPECS, provider_statuses
from app.db.repository import (
    get_evaluation_record,
    list_evaluation_records,
    record_to_evaluation_report,
    save_evaluation_report,
)
from app.db.session import get_db
from app.evaluation.models import InputError
from app.evaluation.pipeline import EvaluationConfig, run_evaluation
from app.evaluation.verify import LLMVerifier, RuleBasedVerifier
from app.providers.mock import MockProvider, UnconfiguredProvider
from app.providers.registry import IMPLEMENTED_PROVIDER_IDS, ProviderRegistry
from app.reporting.export import report_to_csv, report_to_dict, report_to_json

router = APIRouter()
VALID_PROVIDER_NAMES: frozenset[str] = frozenset(s.name for s in PROVIDER_SPECS)


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
    elif cfg.verifier_type == "llm":
        provider_id = (cfg.provider_id or "").strip()
        if not provider_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="provider_id is required when verifier_type is 'llm'.",
            )
        if cfg.model_id is not None:
            model_id = cfg.model_id.strip()
            if not model_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="model_id cannot be empty when specified.",
                )
        if provider_id not in VALID_PROVIDER_NAMES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unknown provider '{provider_id}'. "
                    f"Supported providers: {', '.join(sorted(IMPLEMENTED_PROVIDER_IDS))}."
                ),
            )
        if provider_id not in IMPLEMENTED_PROVIDER_IDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Provider '{provider_id}' adapter is not implemented yet. "
                    f"Implemented adapters: {', '.join(sorted(IMPLEMENTED_PROVIDER_IDS))}."
                ),
            )
        registry = ProviderRegistry.from_env()
        provider = registry.get(provider_id)
        if isinstance(provider, UnconfiguredProvider):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Provider '{provider_id}' is not configured. "
                    "Set the required environment variables and restart the server. "
                    "Check GET /api/providers for configuration status."
                ),
            )
        if cfg.model_id is not None:
            provider.model = cfg.model_id.strip()
        if not provider.model or not str(provider.model).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Provider '{provider_id}' has no model configured. "
                    "Specify a non-empty model_id in the request or set the model environment variable."
                ),
            )
        verifier = LLMVerifier(provider=provider)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported verifier type '{cfg.verifier_type}'. Supported: 'rule_based', 'mock', 'llm'.",
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


@router.get("/evaluations")
def list_evaluations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """List evaluation summaries, newest first, with pagination."""
    records, total = list_evaluation_records(db, limit=limit, offset=offset)
    items = []
    for r in records:
        m = r.metrics_data or {}
        items.append({
            "run_id": r.run_id,
            "created_at": r.created_at,
            "status": r.status,
            "question": r.question[:200],  # truncated for list view
            "metrics": {
                "total_claims": m.get("total_claims", 0),
                "supported": m.get("supported", 0),
                "contradicted": m.get("contradicted", 0),
                "insufficient_evidence": m.get("insufficient_evidence", 0),
                "errors": m.get("errors", 0),
            },
            "config": r.config_data,
        })
    return {"total": total, "offset": offset, "limit": limit, "items": items}


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
