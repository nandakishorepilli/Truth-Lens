import { AlertCircle, RefreshCw } from "lucide-react";

interface Props {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export default function ErrorMessage({
  title = "Request Error",
  message,
  onRetry,
}: Props) {
  return (
    <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 p-4">
      <div className="flex items-start gap-3">
        <AlertCircle className="h-5 w-5 text-rose-400 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-rose-300">{title}</div>
          <div className="mt-1 text-xs text-rose-200/80 break-words leading-relaxed">
            {message}
          </div>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-rose-800/60 bg-rose-900/30 px-3 py-1 text-xs font-medium text-rose-200 hover:bg-rose-900/50 transition-colors"
            >
              <RefreshCw className="h-3 w-3" />
              Try again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
