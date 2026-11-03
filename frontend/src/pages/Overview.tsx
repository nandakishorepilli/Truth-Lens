import { useEffect, useState, useCallback } from "react";
import {
  Activity,
  CheckCircle2,
  XCircle,
  HelpCircle,
  ListOrdered,
  PlusCircle,
  ChevronRight,
  TrendingUp,
  Percent,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import MetricCard from "../components/MetricCard";
import LoadingSpinner from "../components/LoadingSpinner";
import ErrorMessage from "../components/ErrorMessage";
import StatusBadge from "../components/StatusBadge";
import EmptyState from "../components/EmptyState";
import { listEvaluations } from "../api/endpoints";
import type { EvaluationSummary } from "../api/types";
import type { Page } from "../types/navigation";

interface Props {
  navigate: (p: Page) => void;
  refreshTrigger?: number;
}

export default function Overview({ navigate, refreshTrigger }: Props) {
  const [data, setData] = useState<{
    total: number;
    items: EvaluationSummary[];
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listEvaluations(50, 0);
      setData(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load dashboard data";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData, refreshTrigger]);

  const items = data?.items ?? [];
  const totalRuns = data?.total ?? 0;

  // Accurately derive aggregates strictly from retrieved items
  const aggregates = items.reduce(
    (acc, cur) => {
      acc.claims += cur.metrics.total_claims;
      acc.supported += cur.metrics.supported;
      acc.contradicted += cur.metrics.contradicted;
      acc.insufficient += cur.metrics.insufficient_evidence;
      acc.errors += cur.metrics.errors;
      return acc;
    },
    { claims: 0, supported: 0, contradicted: 0, insufficient: 0, errors: 0 }
  );

  const classifiedClaims = aggregates.supported + aggregates.contradicted;
  const supportRate =
    classifiedClaims > 0
      ? `${Math.round((aggregates.supported / (classifiedClaims + aggregates.insufficient)) * 100)}%`
      : "—";

  const pieData = [
    { name: "Supported", value: aggregates.supported, color: "#10b981" },
    { name: "Contradicted", value: aggregates.contradicted, color: "#f43f5e" },
    { name: "Insufficient Evidence", value: aggregates.insufficient, color: "#f59e0b" },
    ...(aggregates.errors > 0
      ? [{ name: "Errors", value: aggregates.errors, color: "#f97316" }]
      : []),
  ].filter((d) => d.value > 0);

  return (
    <div className="space-y-6">
      {/* Top Welcome / Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-text-primary">
            Verification Dashboard
          </h2>
          <p className="text-xs text-text-muted mt-0.5">
            Observability and fact-checking metrics derived from verified evaluations.
          </p>
        </div>
        <button
          onClick={() => navigate({ id: "new-evaluation" })}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-accent-hover transition-all"
        >
          <PlusCircle className="h-4 w-4" />
          New Evaluation
        </button>
      </div>

      {/* Aggregate Metric Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <MetricCard
          label="Total Evaluations"
          value={totalRuns}
          icon={Activity}
          sub={`${items.length} loaded`}
        />
        <MetricCard
          label="Claims Evaluated"
          value={aggregates.claims}
          icon={ListOrdered}
          color="text-accent-light"
          sub="Across evaluations"
        />
        <MetricCard
          label="Supported"
          value={aggregates.supported}
          icon={CheckCircle2}
          color="text-emerald-400"
          sub="Verified by source"
        />
        <MetricCard
          label="Contradicted"
          value={aggregates.contradicted}
          icon={XCircle}
          color="text-rose-400"
          sub="Refuted by source"
        />
        <MetricCard
          label="Insufficient"
          value={aggregates.insufficient}
          icon={HelpCircle}
          color="text-amber-400"
          sub="Evidence missing"
        />
        <MetricCard
          label="Support Rate"
          value={supportRate}
          icon={Percent}
          color="text-accent-light"
          sub="Of total classified"
        />
      </div>

      {loading && <LoadingSpinner size="lg" message="Loading evaluation metrics…" />}
      {error && <ErrorMessage message={error} onRetry={loadData} />}

      {!loading && !error && data && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Claim Verification Distribution Chart */}
          <div className="rounded-xl border border-border bg-bg-card p-5 lg:col-span-1 flex flex-col">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-accent-light" />
                Claim Status Distribution
              </h3>
            </div>
            <p className="text-[11px] text-text-muted mb-4">
              Aggregate breakdown of claim outcomes across loaded evaluations.
            </p>

            {pieData.length > 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center min-h-[220px]">
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={80}
                      paddingAngle={3}
                    >
                      {pieData.map((entry, idx) => (
                        <Cell key={`cell-${idx}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#18181f",
                        border: "1px solid #2a2a35",
                        borderRadius: "8px",
                        fontSize: "12px",
                        color: "#f1f1f5",
                      }}
                      formatter={(val: unknown) => [`${val ?? 0} claims`, "Count"]}
                    />
                    <Legend
                      verticalAlign="bottom"
                      formatter={(val) => (
                        <span className="text-[11px] text-text-secondary">{val}</span>
                      )}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center py-10 text-center">
                <HelpCircle className="h-8 w-8 text-text-muted/40 mb-2" />
                <p className="text-xs text-text-muted">No claim outcome data available yet.</p>
              </div>
            )}
          </div>

          {/* Recent Evaluation Activity */}
          <div className="rounded-xl border border-border bg-bg-card p-5 lg:col-span-2">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-text-primary">
                  Recent Evaluations
                </h3>
                <p className="text-[11px] text-text-muted">
                  Showing latest runs stored in SQLite
                </p>
              </div>
              {items.length > 0 && (
                <button
                  onClick={() => navigate({ id: "history" })}
                  className="text-xs font-medium text-accent-light hover:text-accent flex items-center gap-1 transition-colors"
                >
                  View all history
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            {items.length === 0 ? (
              <EmptyState
                icon={Activity}
                title="No evaluations found"
                description="Your database is currently empty. Start by submitting your first claim evaluation."
                action={
                  <button
                    onClick={() => navigate({ id: "new-evaluation" })}
                    className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-white hover:bg-accent-hover transition-colors"
                  >
                    <PlusCircle className="h-3.5 w-3.5" />
                    Create First Evaluation
                  </button>
                }
              />
            ) : (
              <div className="space-y-2.5">
                {items.slice(0, 6).map((item) => (
                  <div
                    key={item.run_id}
                    onClick={() => navigate({ id: "result", runId: item.run_id })}
                    className="group flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border border-border bg-bg/60 p-3.5 transition-all hover:border-accent/40 hover:bg-bg-card-hover cursor-pointer"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-[10px] text-text-muted">
                          {item.run_id.slice(0, 8)}
                        </span>
                        <StatusBadge status={item.status} size="sm" />
                        <span className="text-[11px] text-text-muted">
                          {new Date(item.created_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                      <p className="text-xs font-medium text-text-primary truncate group-hover:text-accent-light transition-colors">
                        {item.question}
                      </p>
                    </div>

                    <div className="flex items-center gap-4 text-xs">
                      <div className="flex items-center gap-3">
                        <span className="text-text-muted text-[11px]">
                          {item.metrics.total_claims} claims:
                        </span>
                        <span className="text-emerald-400 font-medium">
                          {item.metrics.supported} supp
                        </span>
                        <span className="text-rose-400 font-medium">
                          {item.metrics.contradicted} cont
                        </span>
                        <span className="text-amber-400 font-medium">
                          {item.metrics.insufficient_evidence} ineff
                        </span>
                      </div>
                      <ChevronRight className="h-4 w-4 text-text-muted group-hover:text-accent-light group-hover:translate-x-0.5 transition-all" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
