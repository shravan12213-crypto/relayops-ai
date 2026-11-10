import * as React from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ErrorStateProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  message?: string;
  code?: string;
  onRetry?: () => void;
  isRetrying?: boolean;
}

export function ErrorState({
  title = "Something went wrong",
  message = "An error occurred while loading this data.",
  code,
  onRetry,
  isRetrying = false,
  className,
  ...props
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex min-h-[220px] flex-col items-center justify-center rounded-lg border border-conflict/30 bg-conflict/5 p-6 text-center",
        className,
      )}
      {...props}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-conflict/10 text-conflict">
        <AlertCircle className="h-5 w-5" />
      </div>
      <h3 className="mt-3 text-sm font-semibold text-ink">{title}</h3>
      <p className="mt-1 max-w-sm text-xs text-ink-muted">{message}</p>
      {code && (
        <span className="mt-2 rounded bg-canvas-2 px-2 py-0.5 font-mono text-[10px] text-ink-muted">
          {code}
        </span>
      )}
      {onRetry && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onRetry}
          disabled={isRetrying}
          className="mt-4 gap-1.5 text-xs"
        >
          <RefreshCw className={cn("h-3 w-3", isRetrying && "animate-spin")} />
          <span>{isRetrying ? "Retrying..." : "Retry"}</span>
        </Button>
      )}
    </div>
  );
}
