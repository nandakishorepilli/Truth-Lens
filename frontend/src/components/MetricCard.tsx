import type { LucideIcon } from "lucide-react";

interface Props {
  label: string;
  value: string | number;
  icon: LucideIcon;
  color?: string;
  sub?: string;
  tooltip?: string;
}

export default function MetricCard({
  label,
  value,
  icon: Icon,
  color = "text-accent-light",
  sub,
  tooltip,
}: Props) {
  return (
    <div
      className="rounded-xl border border-border bg-bg-card p-5 transition-all hover:border-border-light shadow-sm"
      title={tooltip}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium uppercase tracking-wider text-text-secondary">
          {label}
        </span>
        <div className={`p-2 rounded-lg bg-bg border border-border/50 ${color}`}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <div>
        <div className={`text-2xl font-bold tracking-tight ${color}`}>
          {value}
        </div>
        {sub && <div className="text-xs text-text-muted mt-1.5">{sub}</div>}
      </div>
    </div>
  );
}
