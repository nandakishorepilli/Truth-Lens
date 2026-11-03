interface Props {
  status: string | null | undefined;
  size?: "sm" | "md";
}

const BADGE_MAP: Record<string, { label: string; className: string }> = {
  SUPPORTED: {
    label: "Supported",
    className: "bg-emerald-950/80 text-emerald-400 border-emerald-800/70",
  },
  CONTRADICTED: {
    label: "Contradicted",
    className: "bg-rose-950/80 text-rose-400 border-rose-800/70",
  },
  INSUFFICIENT_EVIDENCE: {
    label: "Insufficient Evidence",
    className: "bg-amber-950/80 text-amber-400 border-amber-800/70",
  },
  ERROR: {
    label: "Error",
    className: "bg-orange-950/80 text-orange-400 border-orange-800/70",
  },
  completed: {
    label: "Completed",
    className: "bg-emerald-950/80 text-emerald-400 border-emerald-800/70",
  },
  completed_with_errors: {
    label: "Completed (Errors)",
    className: "bg-amber-950/80 text-amber-400 border-amber-800/70",
  },
  failed: {
    label: "Failed",
    className: "bg-rose-950/80 text-rose-400 border-rose-800/70",
  },
};

export default function StatusBadge({ status, size = "md" }: Props) {
  if (!status) return null;

  const cfg = BADGE_MAP[status] ?? {
    label: status.replace(/_/g, " "),
    className: "bg-bg-card text-text-secondary border-border",
  };

  const sizeClass =
    size === "sm"
      ? "text-[11px] px-2 py-0.5 tracking-wide"
      : "text-xs px-2.5 py-1 tracking-normal";

  return (
    <span
      className={`inline-flex items-center font-medium rounded-md border ${sizeClass} ${cfg.className}`}
    >
      {cfg.label}
    </span>
  );
}
