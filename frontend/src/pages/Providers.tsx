import { useEffect, useState, useCallback } from "react";
import {
  Cpu,
  CheckCircle2,
  RefreshCw,
  KeyRound,
  Layers,
  Terminal,
  ShieldCheck,
} from "lucide-react";
import LoadingSpinner from "../components/LoadingSpinner";
import ErrorMessage from "../components/ErrorMessage";
import { getProviders } from "../api/endpoints";
import type { ProviderItem } from "../api/types";

interface Props {
  refreshTrigger?: number;
}

export default function Providers({ refreshTrigger }: Props) {
  const [providers, setProviders] = useState<ProviderItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getProviders();
      setProviders(res.providers);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to load provider statuses";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData, refreshTrigger]);

  const configuredCount = providers.filter((p) => p.configured).length;
  const adapterCount = providers.filter((p) => p.adapter_available).length;

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-2 border-b border-border">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-text-primary">
            LLM Provider Status
          </h2>
          <p className="text-xs text-text-muted mt-0.5">
            Backend adapter availability and environment credential status.
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-bg-card px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary hover:border-border-light transition-all self-start sm:self-auto shadow-sm"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh Providers
        </button>
      </div>

      {/* Summary Chips */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="rounded-xl border border-border bg-bg-card p-4">
          <div className="text-[11px] text-text-muted mb-1">Total Provider Specs</div>
          <div className="text-2xl font-bold text-text-primary">{providers.length}</div>
        </div>
        <div className="rounded-xl border border-border bg-bg-card p-4">
          <div className="text-[11px] text-text-muted mb-1">Configured Credentials</div>
          <div className="text-2xl font-bold text-emerald-400">
            {configuredCount} / {providers.length}
          </div>
        </div>
        <div className="rounded-xl border border-border bg-bg-card p-4">
          <div className="text-[11px] text-text-muted mb-1">HTTP Adapters Implemented</div>
          <div className="text-2xl font-bold text-accent-light">
            {adapterCount} / {providers.length}
          </div>
        </div>
      </div>

      {loading && <LoadingSpinner size="lg" message="Querying provider registry…" />}
      {error && <ErrorMessage message={error} onRetry={loadData} />}

      {!loading && !error && (
        <div className="space-y-3">
          {providers.map((p) => {
            const isOperational = p.configured && p.adapter_available;
            return (
              <div
                key={p.provider}
                className="rounded-xl border border-border bg-bg-card p-5 transition-all hover:border-border-light shadow-sm"
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                  {/* Left: Provider info */}
                  <div className="flex items-start gap-3.5">
                    <div className="rounded-xl bg-bg border border-border p-2.5 shrink-0 mt-0.5">
                      <Cpu className="h-5 w-5 text-accent-light" />
                    </div>

                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-base font-bold text-text-primary capitalize">
                          {p.provider}
                        </span>
                        {isOperational ? (
                          <span className="inline-flex items-center gap-1 rounded bg-emerald-950/80 border border-emerald-800 text-emerald-400 text-[10px] font-semibold px-2 py-0.5">
                            <CheckCircle2 className="h-3 w-3" />
                            Operational
                          </span>
                        ) : p.configured ? (
                          <span className="inline-flex items-center gap-1 rounded bg-amber-950/80 border border-amber-800 text-amber-400 text-[10px] font-semibold px-2 py-0.5">
                            Credentials Present (Adapter Pending)
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded bg-bg border border-border text-text-muted text-[10px] font-medium px-2 py-0.5">
                            Not Configured
                          </span>
                        )}
                      </div>

                      {/* Model & Key info */}
                      <div className="flex items-center gap-4 text-xs text-text-secondary flex-wrap pt-0.5">
                        <div className="flex items-center gap-1">
                          <Layers className="h-3.5 w-3.5 text-text-muted" />
                          <span>Model:</span>
                          <span className="font-mono text-text-primary font-medium">
                            {p.model || <em className="text-text-muted">Unset</em>}
                          </span>
                        </div>

                        {p.key_preview && (
                          <div className="flex items-center gap-1">
                            <KeyRound className="h-3.5 w-3.5 text-text-muted" />
                            <span>Key:</span>
                            <span className="font-mono text-emerald-400 font-medium">
                              {p.key_preview}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Right: Adapter & Config Pills */}
                  <div className="flex sm:flex-col items-end gap-1.5 shrink-0 self-start">
                    <span
                      className={`text-[11px] font-medium px-2.5 py-0.5 rounded-full border ${
                        p.adapter_available
                          ? "bg-accent/15 text-accent-light border-accent/30"
                          : "bg-bg text-text-muted border-border"
                      }`}
                    >
                      {p.adapter_available ? "HTTP Adapter Ready" : "Planned in 3B"}
                    </span>
                    <span
                      className={`text-[11px] font-medium px-2.5 py-0.5 rounded-full border ${
                        p.configured
                          ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/60"
                          : "bg-bg text-text-muted border-border"
                      }`}
                    >
                      {p.configured ? "Key Configured" : "Missing Key"}
                    </span>
                  </div>
                </div>

                {/* Setup Hint if unconfigured */}
                {!p.configured && (
                  <div className="mt-3.5 flex items-start gap-2 rounded-lg border border-border/80 bg-bg/60 px-3.5 py-2 text-xs text-text-muted">
                    <Terminal className="h-3.5 w-3.5 text-accent-light flex-shrink-0 mt-0.5" />
                    <div>
                      <span>Setup hint: </span>
                      <code className="font-mono text-text-secondary bg-bg px-1.5 py-0.2 rounded border border-border text-[11px]">
                        {p.setup_hint}
                      </code>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Security notice */}
      <div className="rounded-xl border border-border bg-bg-card/60 p-4 space-y-1.5">
        <div className="flex items-center gap-2 text-xs font-semibold text-text-primary">
          <ShieldCheck className="h-4 w-4 text-emerald-400" />
          Zero-Exposure Security Guarantee
        </div>
        <p className="text-xs text-text-muted leading-relaxed">
          TruthLens never logs or transmits plaintext API credentials to the browser. Keys are read exclusively by the FastAPI server from local environment files, masked before preview, and redacted in any error stack traces.
        </p>
      </div>
    </div>
  );
}
