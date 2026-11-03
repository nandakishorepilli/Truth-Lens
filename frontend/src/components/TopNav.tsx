import { useEffect, useState, useCallback } from "react";
import { Menu, RefreshCw, Circle, ShieldAlert, Database } from "lucide-react";
import type { Page } from "../types/navigation";
import { getHealth } from "../api/endpoints";

const PAGE_TITLES: Record<string, string> = {
  overview: "Overview",
  "new-evaluation": "New Evaluation",
  result: "Evaluation Result",
  history: "Evaluation History",
  analytics: "Analytics & Distribution",
  providers: "LLM Providers",
};

interface Props {
  page: Page;
  onMenuClick: () => void;
  onRefreshCurrent?: () => void;
}

export default function TopNav({
  page,
  onMenuClick,
  onRefreshCurrent,
}: Props) {
  const [healthStatus, setHealthStatus] = useState<
    "checking" | "healthy" | "degraded" | "offline"
  >("checking");
  const [dbStatus, setDbStatus] = useState<string>("unknown");
  const [isRefreshing, setIsRefreshing] = useState(false);

  const checkHealth = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const h = await getHealth();
      setHealthStatus(h.status === "healthy" ? "healthy" : "degraded");
      setDbStatus(h.database);
    } catch {
      setHealthStatus("offline");
      setDbStatus("disconnected");
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30_000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  const handleManualRefresh = () => {
    checkHealth();
    if (onRefreshCurrent) {
      onRefreshCurrent();
    }
  };

  const statusConfig = {
    checking: {
      color: "text-text-muted",
      fill: "fill-text-muted",
      label: "Checking Backend…",
      badge: "bg-bg text-text-muted border-border",
    },
    healthy: {
      color: "text-emerald-400",
      fill: "fill-emerald-400",
      label: "Backend Connected",
      badge: "bg-emerald-950/60 text-emerald-400 border-emerald-800/60",
    },
    degraded: {
      color: "text-amber-400",
      fill: "fill-amber-400",
      label: "Backend Degraded",
      badge: "bg-amber-950/60 text-amber-400 border-amber-800/60",
    },
    offline: {
      color: "text-rose-400",
      fill: "fill-rose-400",
      label: "Backend Offline",
      badge: "bg-rose-950/60 text-rose-400 border-rose-800/60",
    },
  }[healthStatus];

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-border bg-bg-card/95 backdrop-blur px-4 md:px-6">
      {/* Page Title & Mobile Toggle */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-bg border border-border"
          aria-label="Toggle navigation menu"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-base font-semibold text-text-primary tracking-tight">
            {PAGE_TITLES[page.id] ?? "Dashboard"}
          </h1>
          <p className="text-[11px] text-text-muted hidden sm:block">
            {page.id === "new-evaluation" && "Submit text for claim-by-claim verification"}
            {page.id === "overview" && "High-level summary of verification activity"}
            {page.id === "result" && "Detailed claim breakdown and evidence viewer"}
            {page.id === "history" && "Browse and inspect past evaluation runs"}
            {page.id === "analytics" && "Aggregated accuracy rates and verdict distribution"}
            {page.id === "providers" && "LLM engine status and adapter configuration"}
          </p>
        </div>
      </div>

      {/* Connection & Actions */}
      <div className="flex items-center gap-3">
        {/* Refresh action */}
        <button
          onClick={handleManualRefresh}
          disabled={isRefreshing}
          className="p-2 rounded-lg border border-border bg-bg text-text-secondary hover:text-text-primary hover:border-border-light transition-all disabled:opacity-50"
          title="Refresh current page and health status"
          aria-label="Refresh"
        >
          <RefreshCw
            className={`h-4 w-4 ${isRefreshing ? "animate-spin text-accent-light" : ""}`}
          />
        </button>

        {/* Database indicator */}
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-border bg-bg text-[11px] text-text-secondary">
          <Database className="h-3 w-3 text-text-muted" />
          <span>SQLite: {dbStatus}</span>
        </div>

        {/* Health pill */}
        <div
          className={`flex items-center gap-2 rounded-md border px-2.5 py-1 text-xs font-medium ${statusConfig.badge}`}
        >
          {healthStatus === "offline" ? (
            <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
          ) : (
            <Circle className={`h-2 w-2 ${statusConfig.fill}`} />
          )}
          <span className="hidden sm:inline">{statusConfig.label}</span>
          <span className="sm:hidden capitalize">{healthStatus}</span>
        </div>
      </div>
    </header>
  );
}
