import { useEffect, useState, useCallback } from "react";
import {
  ArrowLeft,
  Download,
  AlertTriangle,
  Clock,
  Layers,
  FileText,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  HelpCircle,
} from "lucide-react";
import LoadingSpinner from "../components/LoadingSpinner";
import ErrorMessage from "../components/ErrorMessage";
import StatusBadge from "../components/StatusBadge";
import ClaimCard from "../components/ClaimCard";
import { getEvaluation, getExportUrl } from "../api/endpoints";
import type { EvaluationReport } from "../api/types";
import type { Page } from "../types/navigation";

interface Props {
  runId: string;
  navigate: (p: Page) => void;
}

export default function EvaluationResult({ runId, navigate }: Props) {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getEvaluation(runId);
      setReport(data);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to load evaluation report";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  if (loading) {
    return (
      <div className="py-24">
        <LoadingSpinner size="lg" message="Loading evaluation report details…" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <button
          onClick={() => navigate({ id: "history" })}
          className="inline-flex items-center gap-1.5 text-xs text-text-muted hover:text-text-primary transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to History
        </button>
        <ErrorMessage
          title="Could Not Retrieve Evaluation"
          message={error}
          onRetry={loadReport}
        />
      </div>
    );
  }

  if (!report) return null;

  const m = report.metrics;
  const verificationsByClaimId = Object.fromEntries(
    report.verifications.map((v) => [v.claim_id, v])
  );

  const sourceTitleMap = Object.fromEntries(
    report.sources.map((s) => [s.id, s.title || s.id])
  );

  const formatRatio = (r?: {
    numerator: number;
    denominator: number;
    value: number | null;
  }) => {
    if (!r || r.value === null) return "—";
    return `${Math.round(r.value * 100)}% (${r.numerator}/${r.denominator})`;
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Navigation & Export Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <button
          onClick={() => navigate({ id: "history" })}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-text-muted hover:text-text-primary transition-colors self-start"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Evaluations
        </button>

        <div className="flex items-center gap-2">
          <a
            href={getExportUrl(report.run_id, "json")}
            download
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-bg-card px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary hover:border-border-light transition-all shadow-sm"
          >
            <Download className="h-3.5 w-3.5 text-accent-light" />
            JSON Export
          </a>
          <a
            href={getExportUrl(report.run_id, "csv")}
            download
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-bg-card px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary hover:border-border-light transition-all shadow-sm"
          >
            <Download className="h-3.5 w-3.5 text-emerald-400" />
            CSV Export
          </a>
        </div>
      </div>

      {/* Primary Report Card */}
      <div className="rounded-xl border border-border bg-bg-card p-6 space-y-5">
        {/* Header meta */}
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 border-b border-border pb-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <StatusBadge status={report.status} />
              <span className="font-mono text-xs text-text-muted bg-bg px-2 py-0.5 rounded border border-border">
                {report.run_id}
              </span>
              <span className="text-xs text-text-muted flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {new Date(report.created_at).toLocaleString()}
              </span>
            </div>
            <h2 className="text-lg font-bold text-text-primary pt-1 leading-snug">
              {report.question}
            </h2>
          </div>

          <div className="text-right sm:text-right text-xs text-text-muted bg-bg/80 border border-border rounded-lg px-3 py-2 shrink-0">
            <div>Engine: <span className="text-text-secondary font-mono">{report.config.verifier}</span></div>
            <div>Extractor: <span className="text-text-secondary font-mono">{report.config.extractor}</span></div>
          </div>
        </div>

        {/* AI Answer preview */}
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-1.5 flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5" />
            Evaluated Answer Text
          </div>
          <div className="rounded-lg border border-border bg-bg/60 p-3.5 text-xs text-text-primary leading-relaxed whitespace-pre-wrap">
            {report.answer}
          </div>
        </div>

        {/* Primary Counts Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
          <div className="rounded-lg border border-border bg-bg p-3">
            <div className="text-[11px] text-text-muted mb-0.5">Total Claims</div>
            <div className="text-xl font-bold text-text-primary">{m.total_claims}</div>
          </div>
          <div className="rounded-lg border border-emerald-950/60 bg-emerald-950/20 p-3">
            <div className="text-[11px] text-emerald-400 mb-0.5 flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3" /> Supported
            </div>
            <div className="text-xl font-bold text-emerald-400">{m.supported}</div>
          </div>
          <div className="rounded-lg border border-rose-950/60 bg-rose-950/20 p-3">
            <div className="text-[11px] text-rose-400 mb-0.5 flex items-center gap-1">
              <XCircle className="h-3 w-3" /> Contradicted
            </div>
            <div className="text-xl font-bold text-rose-400">{m.contradicted}</div>
          </div>
          <div className="rounded-lg border border-amber-950/60 bg-amber-950/20 p-3">
            <div className="text-[11px] text-amber-400 mb-0.5 flex items-center gap-1">
              <HelpCircle className="h-3 w-3" /> Insufficient
            </div>
            <div className="text-xl font-bold text-amber-400">{m.insufficient_evidence}</div>
          </div>
          <div className="rounded-lg border border-border bg-bg p-3">
            <div className="text-[11px] text-text-muted mb-0.5">Errors</div>
            <div className={`text-xl font-bold ${m.errors > 0 ? "text-orange-400" : "text-text-muted"}`}>
              {m.errors}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-bg p-3">
            <div className="text-[11px] text-text-muted mb-0.5">Conflicts</div>
            <div className={`text-xl font-bold ${m.conflicts > 0 ? "text-amber-400" : "text-text-muted"}`}>
              {m.conflicts}
            </div>
          </div>
        </div>

        {/* Verification Ratios with Definitions */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
          <div
            className="rounded-lg border border-border bg-bg p-3"
            title={report.metric_definitions?.supported_claim_rate}
          >
            <div className="text-[11px] text-text-muted mb-1 font-medium">
              Supported Claim Rate
            </div>
            <div className="text-base font-bold text-accent-light">
              {formatRatio(m.supported_claim_rate)}
            </div>
            <p className="text-[10px] text-text-muted mt-1 leading-snug">
              Share of classified claims the evidence supports.
            </p>
          </div>

          <div
            className="rounded-lg border border-border bg-bg p-3"
            title={report.metric_definitions?.evidence_coverage}
          >
            <div className="text-[11px] text-text-muted mb-1 font-medium">
              Evidence Coverage
            </div>
            <div className="text-base font-bold text-emerald-400">
              {formatRatio(m.evidence_coverage)}
            </div>
            <p className="text-[10px] text-text-muted mt-1 leading-snug">
              Claims with at least one supporting or contradicting excerpt.
            </p>
          </div>

          <div
            className="rounded-lg border border-border bg-bg p-3"
            title={report.metric_definitions?.verification_completion_rate}
          >
            <div className="text-[11px] text-text-muted mb-1 font-medium">
              Completion Rate
            </div>
            <div className="text-base font-bold text-text-primary">
              {formatRatio(m.verification_completion_rate)}
            </div>
            <p className="text-[10px] text-text-muted mt-1 leading-snug">
              Claims successfully evaluated without pipeline errors.
            </p>
          </div>
        </div>

        {/* Pipeline Execution Stages */}
        {report.stages && report.stages.length > 0 && (
          <div className="pt-2 border-t border-border/70">
            <div className="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Layers className="h-3 w-3" />
              Pipeline Stages
            </div>
            <div className="flex flex-wrap gap-2">
              {report.stages.map((stg, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1.5 rounded bg-bg border border-border px-2.5 py-1 text-[11px] text-text-secondary"
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  {stg.stage.replace(/_/g, " ")}:{" "}
                  <strong className="text-text-primary capitalize">{stg.state}</strong>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Sources Overview */}
      <div className="rounded-xl border border-border bg-bg-card p-5 space-y-3">
        <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
          <FileText className="h-4 w-4 text-accent-light" />
          Supplied Sources ({report.sources.length})
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {report.sources.map((s) => (
            <div
              key={s.id}
              className="rounded-lg border border-border bg-bg/50 p-3 space-y-1"
            >
              <div className="flex items-center justify-between text-xs font-medium">
                <span className="font-mono text-accent-light">{s.id}</span>
                {s.url && (
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[11px] text-accent-light/80 hover:underline truncate max-w-[200px]"
                  >
                    {s.url}
                  </a>
                )}
              </div>
              {s.title && (
                <div className="text-xs font-semibold text-text-primary">
                  {s.title}
                </div>
              )}
              <div className="text-[11px] text-text-muted line-clamp-2 italic">
                "{s.text}"
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Extracted Claims Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-accent-light" />
            Decomposed Claims ({report.claims.length})
          </h3>
          <span className="text-xs text-text-muted">
            Click any claim to inspect citations and reasoning
          </span>
        </div>

        {report.claims.length === 0 ? (
          <div className="rounded-xl border border-border bg-bg-card p-8 text-center text-xs text-text-muted">
            No factual claims were identified in this response.
          </div>
        ) : (
          <div className="space-y-2.5">
            {report.claims.map((claim) => (
              <ClaimCard
                key={claim.id}
                claim={claim}
                verification={verificationsByClaimId[claim.id]}
                sourceTitles={sourceTitleMap}
              />
            ))}
          </div>
        )}
      </div>

      {/* Skipped Segments if any */}
      {report.skipped && report.skipped.length > 0 && (
        <div className="rounded-xl border border-border bg-bg-card p-5 space-y-2.5">
          <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            Non-Factual / Skipped Segments ({report.skipped.length})
          </div>
          <div className="space-y-1.5">
            {report.skipped.map((seg, idx) => (
              <div
                key={idx}
                className="flex items-start justify-between gap-3 text-xs rounded border border-border/60 bg-bg px-3 py-2"
              >
                <span className="text-text-secondary italic">"{seg.text}"</span>
                <span className="text-[10px] text-text-muted whitespace-nowrap bg-bg-card px-1.5 py-0.5 rounded border border-border">
                  {seg.reason}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Methodological Limitations Notice */}
      {report.limitations && report.limitations.length > 0 && (
        <div className="rounded-xl border border-amber-900/50 bg-amber-950/20 p-5 space-y-2">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-400">
            <AlertTriangle className="h-4 w-4" />
            Verification Limitations & Honest Disclaimers
          </div>
          <ul className="list-disc list-inside space-y-1 text-xs text-amber-300/80 leading-relaxed">
            {report.limitations.map((limitation, i) => (
              <li key={i}>{limitation}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
