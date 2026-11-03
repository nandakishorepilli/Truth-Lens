import {
  Shield,
  LayoutDashboard,
  PlusCircle,
  History,
  BarChart2,
  Cpu,
  X,
  FileCheck2,
} from "lucide-react";
import type { Page } from "../types/navigation";

interface Props {
  page: Page;
  navigate: (p: Page) => void;
  onClose: () => void;
}

const NAV_ITEMS = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "new-evaluation", label: "New Evaluation", icon: PlusCircle },
  { id: "history", label: "Evaluation History", icon: History },
  { id: "analytics", label: "Analytics", icon: BarChart2 },
  { id: "providers", label: "Providers", icon: Cpu },
] as const;

export default function Sidebar({ page, navigate, onClose }: Props) {
  return (
    <div className="flex h-full flex-col bg-bg-card border-r border-border">
      {/* Brand Header */}
      <div className="flex items-center justify-between px-5 py-5 border-b border-border">
        <div
          className="flex items-center gap-3 cursor-pointer group"
          onClick={() => {
            navigate({ id: "overview" });
            onClose();
          }}
        >
          <div className="rounded-xl bg-gradient-to-br from-accent to-accent-hover p-2 shadow-md shadow-accent/20 group-hover:scale-105 transition-transform">
            <Shield className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-base font-bold text-text-primary tracking-tight">
                TruthLens
              </span>
              <span className="rounded bg-accent/20 text-accent-light text-[10px] font-semibold px-1.5 py-0.2">
                v0.1
              </span>
            </div>
            <div className="text-[10px] uppercase tracking-wider text-text-muted font-medium">
              Factual Verification
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          className="lg:hidden p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-bg transition-colors"
          aria-label="Close sidebar"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Nav Menu */}
      <nav className="flex-1 space-y-1.5 px-3 py-4 overflow-y-auto">
        <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
          Dashboard
        </div>
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
          const active =
            page.id === id || (id === "history" && page.id === "result");
          return (
            <button
              key={id}
              onClick={() => {
                navigate({ id } as Page);
                onClose();
              }}
              className={`w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all text-left ${
                active
                  ? "bg-accent/15 text-accent-light border border-accent/30 shadow-sm"
                  : "text-text-secondary hover:bg-bg-card-hover hover:text-text-primary"
              }`}
            >
              <Icon
                className={`h-4.5 w-4.5 flex-shrink-0 ${
                  active ? "text-accent-light" : "text-text-muted"
                }`}
              />
              <span className="flex-1 truncate">{label}</span>
              {id === "new-evaluation" && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/20 text-accent-light">
                  New
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Observability Badge & Footer */}
      <div className="p-4 border-t border-border bg-bg/40 space-y-3">
        <div className="rounded-lg border border-border/80 bg-bg-card p-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-text-primary mb-1">
            <FileCheck2 className="h-3.5 w-3.5 text-accent-light" />
            AI Observability
          </div>
          <p className="text-[11px] text-text-muted leading-relaxed">
            Measures verifiable claim support against supplied evidence.
          </p>
        </div>

        <div className="flex items-center justify-between text-[11px] text-text-muted px-1">
          <span>TruthLens Engine</span>
          <span className="font-mono text-emerald-400">Offline-ready</span>
        </div>
      </div>
    </div>
  );
}
