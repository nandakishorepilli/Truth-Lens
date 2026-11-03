import { useEffect, useState, useCallback, useMemo } from "react";
import {
  History as HistoryIcon,
  Search,
  ChevronLeft,
  ChevronRight,
  PlusCircle,
  FileText,
} from "lucide-react";
import LoadingSpinner from "../components/LoadingSpinner";
import ErrorMessage from "../components/ErrorMessage";
import EmptyState from "../components/EmptyState";
import StatusBadge from "../components/StatusBadge";
import { listEvaluations } from "../api/endpoints";
import type { EvaluationSummary } from "../api/types";
import type { Page } from "../types/navigation";

interface Props {
  navigate: (p: Page) => void;
  refreshTrigger?: number;
}

const PAGE_SIZE = 15;

export default function History({ navigate, refreshTrigger }: Props) {
  const [items, setItems] = useState<EvaluationSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [pageIndex, setPageIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Client-side search and status filter
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const loadData = useCallback(async (offset: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await listEvaluations(PAGE_SIZE, offset);
      setItems(res.items);
      setTotal(res.total);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to load evaluation history";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData(pageIndex * PAGE_SIZE);
  }, [loadData, pageIndex, refreshTrigger]);

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const matchesSearch =
        searchQuery === "" ||
        item.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.run_id.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesStatus =
        statusFilter === "all" || item.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [items, searchQuery, statusFilter]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-5">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-text-primary">
            Evaluation History
          </h2>
          <p className="text-xs text-text-muted mt-0.5">
            Audit trail of all claim verification runs persisted in SQLite database.
          </p>
        </div>
        <button
          onClick={() => navigate({ id: "new-evaluation" })}
          className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-xs font-semibold text-white hover:bg-accent-hover transition-all self-start sm:self-auto shadow-sm"
        >
          <PlusCircle className="h-4 w-4" />
          New Evaluation
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-text-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by question or run ID…"
            className="w-full rounded-lg border border-border bg-bg-card pl-9 pr-3 py-2 text-xs text-text-primary placeholder:text-text-muted/60 focus:border-accent focus:outline-none"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-border bg-bg-card px-3 py-2 text-xs text-text-primary focus:border-accent focus:outline-none w-full sm:w-auto"
        >
          <option value="all">All Statuses</option>
          <option value="completed">Completed</option>
          <option value="completed_with_errors">Completed (with errors)</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {loading && <LoadingSpinner size="lg" message="Loading evaluation history…" />}
      {error && <ErrorMessage message={error} onRetry={() => loadData(pageIndex * PAGE_SIZE)} />}

      {!loading && !error && (
        <>
          {filteredItems.length === 0 ? (
            <EmptyState
              icon={HistoryIcon}
              title={
                items.length === 0
                  ? "No evaluation runs stored"
                  : "No evaluations match filter"
              }
              description={
                items.length === 0
                  ? "Completed evaluations will be stored and listed here with full audit reports."
                  : "Try clearing your search query or changing the status filter."
              }
              action={
                items.length === 0 ? (
                  <button
                    onClick={() => navigate({ id: "new-evaluation" })}
                    className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-white hover:bg-accent-hover transition-colors"
                  >
                    <PlusCircle className="h-3.5 w-3.5" />
                    Run First Evaluation
                  </button>
                ) : undefined
              }
            />
          ) : (
            <div className="rounded-xl border border-border bg-bg-card overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-border bg-bg/70 text-text-muted">
                    <tr>
                      <th className="px-4 py-3 font-semibold uppercase tracking-wider text-[10px]">
                        Run ID
                      </th>
                      <th className="px-4 py-3 font-semibold uppercase tracking-wider text-[10px]">
                        Question
                      </th>
                      <th className="px-4 py-3 font-semibold uppercase tracking-wider text-[10px]">
                        Created At
                      </th>
                      <th className="px-4 py-3 font-semibold uppercase tracking-wider text-[10px]">
                        Status
                      </th>
                      <th className="px-4 py-3 font-semibold uppercase tracking-wider text-[10px] text-right">
                        Claims (S / C / I)
                      </th>
                      <th className="px-4 py-3 font-semibold uppercase tracking-wider text-[10px] text-right">
                        Action
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {filteredItems.map((item) => {
                      const m = item.metrics;
                      return (
                        <tr
                          key={item.run_id}
                          onClick={() =>
                            navigate({ id: "result", runId: item.run_id })
                          }
                          className="hover:bg-bg-card-hover/80 cursor-pointer transition-colors group"
                        >
                          <td className="px-4 py-3.5 font-mono text-[11px] text-text-muted">
                            {item.run_id.slice(0, 8)}…
                          </td>
                          <td className="px-4 py-3.5 font-medium text-text-primary max-w-sm truncate group-hover:text-accent-light transition-colors">
                            {item.question}
                          </td>
                          <td className="px-4 py-3.5 text-text-muted whitespace-nowrap">
                            {new Date(item.created_at).toLocaleDateString(
                              undefined,
                              {
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              }
                            )}
                          </td>
                          <td className="px-4 py-3.5 whitespace-nowrap">
                            <StatusBadge status={item.status} size="sm" />
                          </td>
                          <td className="px-4 py-3.5 text-right whitespace-nowrap font-medium">
                            <span className="text-text-primary">
                              {m.total_claims}
                            </span>{" "}
                            <span className="text-text-muted">claims</span>{" "}
                            <span className="text-emerald-400">({m.supported}</span>/
                            <span className="text-rose-400">{m.contradicted}</span>/
                            <span className="text-amber-400">{m.insufficient_evidence})</span>
                          </td>
                          <td className="px-4 py-3.5 text-right">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate({ id: "result", runId: item.run_id });
                              }}
                              className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-[11px] text-text-secondary hover:text-text-primary hover:border-border-light transition-all"
                            >
                              <FileText className="h-3 w-3" />
                              Report
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Pagination controls */}
              <div className="flex items-center justify-between border-t border-border bg-bg/50 px-4 py-3 text-xs text-text-muted">
                <div>
                  Showing {filteredItems.length} of {total} total runs
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
                    disabled={pageIndex === 0}
                    className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs text-text-secondary hover:bg-bg disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                    Previous
                  </button>
                  <span className="px-2 font-medium text-text-primary">
                    Page {pageIndex + 1} of {totalPages}
                  </span>
                  <button
                    onClick={() => setPageIndex((p) => p + 1)}
                    disabled={pageIndex + 1 >= totalPages}
                    className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs text-text-secondary hover:bg-bg disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                  >
                    Next
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
