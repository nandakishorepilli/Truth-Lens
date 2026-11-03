import { useEffect, useState, useCallback } from "react";
import {
  BarChart2,
  PieChart as PieIcon,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Info,
  TrendingUp,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  CartesianGrid,
} from "recharts";
import LoadingSpinner from "../components/LoadingSpinner";
import ErrorMessage from "../components/ErrorMessage";
import EmptyState from "../components/EmptyState";
import MetricCard from "../components/MetricCard";
import { listEvaluations } from "../api/endpoints";
import type { EvaluationSummary } from "../api/types";

interface Props {
  refreshTrigger?: number;
}

export default function Analytics({ refreshTrigger }: Props) {
  const [items, setItems] = useState<EvaluationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch up to 200 items for statistical analytics
      const res = await listEvaluations(200, 0);
      setItems(res.items);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to load analytics data";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData, refreshTrigger]);

  if (loading) {
    return (
      <div className="py-24">
        <LoadingSpinner size="lg" message="Computing verification analytics…" />
      </div>
    );
  }

  if (error) {
    return <ErrorMessage message={error} onRetry={loadData} />;
  }

  if (items.length === 0) {
    return (
      <EmptyState
        icon={BarChart2}
        title="No evaluation records for analytics"
        description="Run one or more evaluations to visualize claim status distributions and accuracy rates."
      />
    );
  }

  // Aggregate totals
  const totals = items.reduce(
    (acc, cur) => {
      acc.totalClaims += cur.metrics.total_claims;
      acc.supported += cur.metrics.supported;
      acc.contradicted += cur.metrics.contradicted;
      acc.insufficient += cur.metrics.insufficient_evidence;
      acc.errors += cur.metrics.errors;
      return acc;
    },
    { totalClaims: 0, supported: 0, contradicted: 0, insufficient: 0, errors: 0 }
  );

  const classified = totals.supported + totals.contradicted + totals.insufficient;
  const supportPct =
    classified > 0 ? Math.round((totals.supported / classified) * 100) : null;
  const contradictionPct =
    classified > 0 ? Math.round((totals.contradicted / classified) * 100) : null;
  const insufficientPct =
    classified > 0 ? Math.round((totals.insufficient / classified) * 100) : null;

  const avgClaimsPerRun =
    items.length > 0 ? (totals.totalClaims / items.length).toFixed(1) : "0";

  // Pie chart data
  const pieData = [
    { name: "Supported Claims", value: totals.supported, color: "#10b981" },
    { name: "Contradicted Claims", value: totals.contradicted, color: "#f43f5e" },
    { name: "Insufficient Evidence", value: totals.insufficient, color: "#f59e0b" },
    ...(totals.errors > 0
      ? [{ name: "Errors", value: totals.errors, color: "#f97316" }]
      : []),
  ].filter((d) => d.value > 0);

  // Bar chart data: newest 15 runs in chronological order (oldest -> newest)
  const barData = [...items]
    .slice(0, 15)
    .reverse()
    .map((item, idx) => ({
      name: `Eval #${idx + 1}`,
      Supported: item.metrics.supported,
      Contradicted: item.metrics.contradicted,
      Insufficient: item.metrics.insufficient_evidence,
      total: item.metrics.total_claims,
    }));

  const tooltipStyle = {
    backgroundColor: "#18181f",
    border: "1px solid #2a2a35",
    borderRadius: "8px",
    color: "#f1f1f5",
    fontSize: "12px",
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h2 className="text-xl font-bold tracking-tight text-text-primary">
          Evaluation Analytics
        </h2>
        <p className="text-xs text-text-muted mt-0.5">
          Empirical verification metrics calculated from {items.length} evaluation runs.
        </p>
      </div>

      {/* Aggregate Metric Highlights */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <MetricCard
          label="Supported Share"
          value={supportPct !== null ? `${supportPct}%` : "—"}
          icon={CheckCircle2}
          color="text-emerald-400"
          sub={`${totals.supported} / ${classified} claims`}
        />
        <MetricCard
          label="Contradicted Share"
          value={contradictionPct !== null ? `${contradictionPct}%` : "—"}
          icon={XCircle}
          color="text-rose-400"
          sub={`${totals.contradicted} / ${classified} claims`}
        />
        <MetricCard
          label="Insufficient Share"
          value={insufficientPct !== null ? `${insufficientPct}%` : "—"}
          icon={HelpCircle}
          color="text-amber-400"
          sub={`${totals.insufficient} / ${classified} claims`}
        />
        <MetricCard
          label="Avg Claims / Run"
          value={avgClaimsPerRun}
          icon={TrendingUp}
          color="text-accent-light"
          sub={`${totals.totalClaims} claims total`}
        />
        <MetricCard
          label="Total Runs"
          value={items.length}
          icon={BarChart2}
          color="text-text-primary"
          sub="Stored in database"
        />
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Status Distribution Pie */}
        <div className="rounded-xl border border-border bg-bg-card p-5 lg:col-span-2 flex flex-col">
          <div className="flex items-center gap-2 text-sm font-semibold text-text-primary mb-1">
            <PieIcon className="h-4 w-4 text-accent-light" />
            Claim Status Distribution
          </div>
          <p className="text-[11px] text-text-muted mb-4">
            Proportion of all verified claims across {items.length} evaluated runs.
          </p>

          <div className="flex-1 flex flex-col items-center justify-center min-h-[260px]">
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={90}
                  paddingAngle={3}
                >
                  {pieData.map((entry, idx) => (
                    <Cell key={`pie-cell-${idx}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend
                  verticalAlign="bottom"
                  formatter={(val) => (
                    <span className="text-[11px] text-text-secondary">{val}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Claim Breakdown Bar Chart */}
        <div className="rounded-xl border border-border bg-bg-card p-5 lg:col-span-3 flex flex-col">
          <div className="flex items-center gap-2 text-sm font-semibold text-text-primary mb-1">
            <BarChart2 className="h-4 w-4 text-accent-light" />
            Claims per Evaluation (Recent 15 Runs)
          </div>
          <p className="text-[11px] text-text-muted mb-4">
            Decomposed claim outcomes for recent evaluation jobs.
          </p>

          <div className="flex-1 min-h-[260px]">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={barData} barSize={16}>
                <CartesianGrid stroke="#2a2a35" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 10, fill: "#9ca3af" }}
                  axisLine={{ stroke: "#2a2a35" }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#9ca3af" }}
                  axisLine={{ stroke: "#2a2a35" }}
                  tickLine={false}
                  allowDecimals={false}
                />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend
                  verticalAlign="top"
                  align="right"
                  formatter={(val) => (
                    <span className="text-[11px] text-text-secondary">{val}</span>
                  )}
                />
                <Bar dataKey="Supported" fill="#10b981" radius={[3, 3, 0, 0]} />
                <Bar dataKey="Contradicted" fill="#f43f5e" radius={[3, 3, 0, 0]} />
                <Bar dataKey="Insufficient" fill="#f59e0b" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Observability Philosophy Disclaimer */}
      <div className="rounded-xl border border-border bg-bg-card/70 p-4 flex items-start gap-3">
        <Info className="h-4 w-4 text-accent-light flex-shrink-0 mt-0.5" />
        <div className="text-xs text-text-muted leading-relaxed">
          <strong className="text-text-primary">Methodological Interpretation:</strong>{" "}
          "Supported" claim rates strictly measure lexical/semantic alignment between AI output claims and the specific reference texts provided by the evaluator. High support does not establish ground-truth omniscience; it validates strict grounding in the supplied citations.
        </div>
      </div>
    </div>
  );
}
