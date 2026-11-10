import * as React from "react";
import { CheckCircle2, Loader2, AlertCircle } from "lucide-react";

import { cn } from "@/lib/utils";

export interface JobProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  stage?: string;
  progress?: number; // 0 - 100
  status?: "pending" | "running" | "completed" | "failed";
  error?: string | null;
}

const DEFAULT_STAGES = [
  "connect_check",
  "redact_audit",
  "entities",
  "graph",
  "extract",
  "verify_citations",
  "conflicts",
  "ambiguities",
  "scorecard",
  "draft_plan",
  "snapshot_v1",
];

const STAGE_LABELS: Record<string, string> = {
  connect_check: "Connect Check",
  redact_audit: "Redact Audit",
  entities: "Entities",
  graph: "Graph",
  extract: "Extract",
  verify_citations: "Verify Citations",
  conflicts: "Conflicts",
  ambiguities: "Ambiguities",
  scorecard: "Scorecard",
  draft_plan: "Draft Plan",
  snapshot_v1: "Snapshot v1",
};

export function JobProgress({
  stage = "connect_check",
  progress = 0,
  status = "running",
  error,
  className,
  ...props
}: JobProgressProps) {
  const currentStageIndex = Math.max(0, DEFAULT_STAGES.indexOf(stage));
  const normalizedProgress = Math.min(100, Math.max(0, progress));

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "w-full space-y-3 rounded-lg border bg-card p-4 text-ink shadow-sm",
        className,
      )}
      {...props}
    >
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          {status === "running" && <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />}
          {status === "completed" && <CheckCircle2 className="h-3.5 w-3.5 text-verified" />}
          {status === "failed" && <AlertCircle className="h-3.5 w-3.5 text-conflict" />}
          <span className="font-medium text-ink">Stage: {STAGE_LABELS[stage] || stage}</span>
        </div>
        <span className="font-mono text-ink-muted">{normalizedProgress}%</span>
      </div>

      {/* Progress bar */}
      <div className="h-2 w-full overflow-hidden rounded-full bg-canvas-2">
        <div
          className={cn(
            "h-full transition-all duration-300 ease-in-out",
            status === "completed"
              ? "bg-verified"
              : status === "failed"
                ? "bg-conflict"
                : "bg-primary",
          )}
          style={{ width: `${normalizedProgress}%` }}
        />
      </div>

      {/* Stages micro-stepper */}
      <div className="hidden grid-cols-11 gap-1 pt-1 md:grid">
        {DEFAULT_STAGES.map((s, idx) => {
          const isDone = idx < currentStageIndex || status === "completed";
          const isCurrent = idx === currentStageIndex && status === "running";
          return (
            <div
              key={s}
              title={STAGE_LABELS[s] || s}
              className={cn(
                "h-1 rounded-sm transition-colors",
                isDone ? "bg-verified/80" : isCurrent ? "bg-primary animate-pulse" : "bg-canvas-2",
              )}
            />
          );
        })}
      </div>

      {error && (
        <p className="rounded bg-conflict/10 p-2 text-xs text-conflict border border-conflict/20">
          {error}
        </p>
      )}
    </div>
  );
}
