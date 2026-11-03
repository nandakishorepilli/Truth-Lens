interface Props {
  size?: "sm" | "md" | "lg";
  message?: string;
}

export default function LoadingSpinner({ size = "md", message }: Props) {
  const dimension = {
    sm: "h-4 w-4 border-2",
    md: "h-6 w-6 border-2",
    lg: "h-10 w-10 border-3",
  }[size];

  return (
    <div className="flex flex-col items-center justify-center gap-3 py-6">
      <div
        className={`${dimension} animate-spin rounded-full border-border border-t-accent-light`}
        role="status"
        aria-label="Loading"
      />
      {message && <p className="text-xs text-text-muted">{message}</p>}
    </div>
  );
}
