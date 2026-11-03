import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  XCircle,
  HelpCircle,
  AlertOctagon,
  FileText,
  Sparkles,
} from "lucide-react";
import StatusBadge from "./StatusBadge";
import type { Claim, Verification } from "../api/types";

interface Props {
  claim: Claim;
  verification?: Verification;
  sourceTitles?: Record<string, string>;
}

export default function ClaimCard({
  claim,
  verification,
  sourceTitles = {},
}: Props) {
  const [expanded, setExpanded] = useState(false);

  const cls = verification?.classification;
  const isError = verification?.status === "ERROR";
  const hasSupporting = (verification?.supporting ?? []).length > 0;
  const hasContradicting = (verification?.contradicting ?? []).length > 0;
  const hasDetails =
    Boolean(verification) &&
    (hasSupporting ||
      hasContradicting ||
      Boolean(verification?.reasoning) ||
      Boolean(verification?.error) ||
      verification?.conflict);

  const getBorderColor = () => {
    if (isError) return "border-orange-900/40 hover:border-orange-800/60";
    if (cls === "SUPPORTED") return "border-emerald-950 hover:border-emerald-800/60";
    if (cls === "CONTRADICTED") return "border-rose-950 hover:border-rose-800/60";
    if (cls === "INSUFFICIENT_EVIDENCE") return "border-amber-950 hover:border-amber-800/60";
    return "border-border hover:border-border-light";
  };

  const getStatusIcon = () => {
    if (isError) return <AlertOctagon className="h-4 w-4 text-orange-400" />;
    if (cls === "SUPPORTED") return <CheckCircle2 className="h-4 w-4 text-emerald-400" />;
    if (cls === "CONTRADICTED") return <XCircle className="h-4 w-4 text-rose-400" />;
    if (cls === "INSUFFICIENT_EVIDENCE") return <HelpCircle className="h-4 w-4 text-amber-400" />;
    return <FileText className="h-4 w-4 text-text-muted" />;
  };

  return (
    <div
      className={`rounded-xl border bg-bg-card transition-all overflow-hidden ${getBorderColor()}`}
    >
      <div
        onClick={() => hasDetails && setExpanded(!expanded)}
        className={`w-full flex items-start gap-3 p-4 text-left transition-colors ${
          hasDetails ? "cursor-pointer hover:bg-bg-card-hover" : ""
        }`}
      >
        <div className="flex-shrink-0 mt-0.5">
          {hasDetails ? (
            expanded ? (
              <ChevronDown className="h-4 w-4 text-text-muted" />
            ) : (
              <ChevronRight className="h-4 w-4 text-text-muted" />
            )
          ) : (
            <div className="w-4 h-4" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            <span className="font-mono text-xs font-semibold text-text-muted bg-bg px-2 py-0.5 rounded border border-border">
              {claim.id}
            </span>
            <div className="flex items-center gap-1.5">
              {getStatusIcon()}
              <StatusBadge
                status={isError ? "ERROR" : cls ?? null}
                size="sm"
              />
            </div>
            {verification?.conflict && (
              <span className="text-[11px] font-medium bg-amber-950/80 text-amber-400 border border-amber-800/70 px-2 py-0.5 rounded-md">
                Conflicting Sources
              </span>
            )}
            {verification?.confidence !== null &&
              verification?.confidence !== undefined && (
                <span className="text-xs text-text-muted">
                  Confidence: {Math.round(verification.confidence * 100)}%
                </span>
              )}
            {verification?.method && (
              <span className="text-[11px] text-text-muted ml-auto hidden sm:inline">
                via {verification.method}
              </span>
            )}
          </div>

          <p className="text-sm font-medium text-text-primary leading-relaxed">
            {claim.text}
          </p>
        </div>
      </div>

      {expanded && verification && (
        <div className="border-t border-border/80 bg-bg/40 px-5 py-4 space-y-4">
          {/* Reasoning */}
          {verification.reasoning && (
            <div>
              <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted mb-1.5">
                <Sparkles className="h-3 w-3 text-accent-light" />
                Verification Reasoning
              </div>
              <p className="text-xs text-text-secondary leading-relaxed bg-bg-card border border-border/70 rounded-lg p-3">
                {verification.reasoning}
              </p>
            </div>
          )}

          {/* Supporting Evidence */}
          {hasSupporting && (
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-emerald-400 mb-2 flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Supporting Evidence ({verification.supporting.length})
              </div>
              <div className="space-y-2">
                {verification.supporting.map((ev, i) => (
                  <div
                    key={i}
                    className="rounded-lg border border-emerald-900/40 bg-emerald-950/20 p-3"
                  >
                    <div className="flex items-center justify-between text-[11px] text-emerald-300/80 mb-1">
                      <span className="font-semibold">
                        Source {ev.source_id}
                        {sourceTitles[ev.source_id]
                          ? ` · ${sourceTitles[ev.source_id]}`
                          : ""}
                      </span>
                      <span className="font-mono text-[10px] text-emerald-400/60">
                        chars {ev.start}:{ev.end}
                      </span>
                    </div>
                    <blockquote className="text-xs text-text-primary italic border-l-2 border-emerald-700/60 pl-2.5 my-1">
                      "{ev.excerpt}"
                    </blockquote>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Contradicting Evidence */}
          {hasContradicting && (
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-rose-400 mb-2 flex items-center gap-1.5">
                <XCircle className="h-3.5 w-3.5" />
                Contradicting Evidence ({verification.contradicting.length})
              </div>
              <div className="space-y-2">
                {verification.contradicting.map((ev, i) => (
                  <div
                    key={i}
                    className="rounded-lg border border-rose-900/40 bg-rose-950/20 p-3"
                  >
                    <div className="flex items-center justify-between text-[11px] text-rose-300/80 mb-1">
                      <span className="font-semibold">
                        Source {ev.source_id}
                        {sourceTitles[ev.source_id]
                          ? ` · ${sourceTitles[ev.source_id]}`
                          : ""}
                      </span>
                      <span className="font-mono text-[10px] text-rose-400/60">
                        chars {ev.start}:{ev.end}
                      </span>
                    </div>
                    <blockquote className="text-xs text-text-primary italic border-l-2 border-rose-700/60 pl-2.5 my-1">
                      "{ev.excerpt}"
                    </blockquote>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error Details */}
          {verification.error && (
            <div className="rounded-lg border border-orange-900/50 bg-orange-950/20 p-3">
              <div className="text-[11px] font-semibold text-orange-400 uppercase tracking-wider mb-1">
                Verification Pipeline Error
              </div>
              <p className="text-xs font-mono text-orange-300/90 break-words">
                {verification.error}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
