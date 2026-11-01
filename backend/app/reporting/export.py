"""JSON and CSV report export. All strings pass through secret redaction."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from app.core.redaction import redact_obj
from app.evaluation.metrics import METRIC_DEFINITIONS
from app.evaluation.pipeline import EvaluationReport

CSV_COLUMNS = ["claim_id", "claim_text", "position", "status", "classification", "conflict",
               "supporting_evidence", "contradicting_evidence", "reasoning", "confidence", "error", "method"]
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _plain(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _plain(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    return obj


def report_to_dict(report: EvaluationReport) -> dict:
    data = _plain(report)
    data["metric_definitions"] = METRIC_DEFINITIONS
    data["limitations"] = list(report.limitations)
    return redact_obj(data)


def report_to_json(report: EvaluationReport) -> str:
    return json.dumps(report_to_dict(report), indent=2, ensure_ascii=False)


def _safe_cell(value: Any) -> str:
    s = "" if value is None else str(value)
    # Prevent spreadsheet formula injection when the CSV is opened in Excel/Sheets.
    return "'" + s if s.startswith(_FORMULA_PREFIXES) else s


def report_to_csv(report: EvaluationReport) -> str:
    data = report_to_dict(report)
    by_claim = {v["claim_id"]: v for v in data["verifications"]}
    fmt = lambda ev: " | ".join(f"{e['source_id']}: {e['excerpt']}" for e in ev)  # noqa: E731
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for c in data["claims"]:
        v = by_claim.get(c["id"], {})
        w.writerow([_safe_cell(x) for x in (
            c["id"], c["text"], c["position"], v.get("status"), v.get("classification"), v.get("conflict"),
            fmt(v.get("supporting", [])), fmt(v.get("contradicting", [])), v.get("reasoning"),
            v.get("confidence"), v.get("error"), v.get("method"))])
    return out.getvalue()
