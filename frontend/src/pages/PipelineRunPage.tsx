import * as React from "react";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Loader2,
  Play,
  RefreshCw,
  Terminal,
} from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useHandover, useRetryPipeline, useRunPipeline } from "@/lib/api/handovers";
import { useJob } from "@/lib/api/jobs";
import { cn } from "@/lib/utils";

interface PipelineStageDef {
  id: string;
  label: string;
  description: string;
  expectedWeight: number; // approximate progress % target
}

const PIPELINE_STAGES: PipelineStageDef[] = [
  {
    id: "connect_check",
    label: "1. Connect Check",
    description: "Verify source connectivity and check for ingested raw events.",
    expectedWeight: 5,
  },
  {
    id: "redact_audit",
    label: "2. Redaction Audit",
    description: "Scrub secrets, API keys, credentials, and personal identifiers.",
    expectedWeight: 15,
  },
  {
    id: "entities",
    label: "3. Entity Resolution",
    description: "Merge cross-platform developer aliases and top-level modules.",
    expectedWeight: 25,
  },
  {
    id: "graph",
    label: "4. Temporal & Ownership Graph",
    description: "Build commit, PR, issue, and file dependency edges.",
    expectedWeight: 35,
  },
  {
    id: "extract",
    label: "5. Claim Extraction",
    description: "Derive candidate decisions, runbooks, and ownership statements.",
    expectedWeight: 50,
  },
  {
    id: "verify_citations",
    label: "6. Citation Binding & Validation",
    description: "Verify artifact IDs and bind exact substring snippet offsets.",
    expectedWeight: 65,
  },
  {
    id: "conflicts",
    label: "7. Contradiction Detection",
    description: "Identify numerical mismatches and architectural conflicts.",
    expectedWeight: 75,
  },
  {
    id: "ambiguities",
    label: "8. Ambiguity Ledger",
    description: "Surface gaps, low evidence merges, and unverified assertions.",
    expectedWeight: 85,
  },
  {
    id: "scorecard",
    label: "9. Readiness Scorecard",
    description: "Compute handover verification metrics and authority breakdown.",
    expectedWeight: 92,
  },
  {
    id: "draft_plan",
    label: "10. Successor Onboarding Plan",
    description: "Synthesize guided reading sequence and comprehension checklist.",
    expectedWeight: 97,
  },
  {
    id: "snapshot_v1",
    label: "11. Cryptographic Snapshot v1",
    description: "Freeze verified claims and compute SHA-256 state hash.",
    expectedWeight: 100,
  },
];

interface LogEntry {
  ts: string;
  stage?: string;
  progress?: number;
  message: string;
}

export function PipelineRunPage() {
  const { handoverId } = useParams<{ handoverId: string }>();
  const navigate = useNavigate();
  const { data: handover, isLoading: handoverLoading } = useHandover(handoverId);

  // Active Job State
  const [activeJobId, setActiveJobId] = React.useState<string | null>(() => {
    return sessionStorage.getItem(`relayops-job-${handoverId}`) || null;
  });

  const { data: job, refetch: refetchJob } = useJob(activeJobId || undefined);
  const runPipeline = useRunPipeline();
  const retryPipeline = useRetryPipeline();

  const [logs, setLogs] = React.useState<LogEntry[]>([]);
  const [logsExpanded, setLogsExpanded] = React.useState(true);
  const [elapsedSeconds, setElapsedSeconds] = React.useState(0);
  const [timerActive, setTimerActive] = React.useState(false);
  const [selectedRetryStage, setSelectedRetryStage] = React.useState<string>("connect_check");

  // Keep logs in sync with job.log from polling or initial fetch
  React.useEffect(() => {
    if (job?.log && Array.isArray(job.log)) {
      setLogs(job.log as unknown as LogEntry[]);
    }
  }, [job?.log]);

  // Elapsed time counter
  React.useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (timerActive) {
      interval = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [timerActive]);

  // Start or stop timer based on status
  React.useEffect(() => {
    const isRunning =
      job?.status === "running" || job?.status === "queued" || runPipeline.isPending;
    setTimerActive(isRunning);
  }, [job?.status, runPipeline.isPending]);

  // SSE Real-Time Event Subscription with reconnect logic
  React.useEffect(() => {
    if (!activeJobId) return;

    let eventSource: EventSource | null = null;
    let reconnectTimeout: NodeJS.Timeout | null = null;

    const connectSSE = () => {
      // EventSource with cookie credentials automatically sent
      eventSource = new EventSource(`/api/v1/jobs/${activeJobId}/events`);

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.message) {
            setLogs((prev) => {
              // Avoid duplicates
              if (prev.some((l) => l.ts === data.ts && l.message === data.message)) {
                return prev;
              }
              return [...prev, data];
            });
          }
          // Refresh job query cache on milestone
          if (data.status || data.stage) {
            refetchJob();
          }
        } catch {
          // Non-JSON message or heartbeat ping
        }
      };

      eventSource.onerror = () => {
        if (eventSource) {
          eventSource.close();
        }
        // Auto-reconnect after 3 seconds if job is not terminal
        if (job?.status !== "done" && job?.status !== "failed") {
          reconnectTimeout = setTimeout(connectSSE, 3000);
        }
      };
    };

    connectSSE();

    return () => {
      if (eventSource) eventSource.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [activeJobId, job?.status, refetchJob]);

  // Handler to start pipeline
  const handleStartPipeline = async (fromStage?: string) => {
    if (!handoverId) return;
    try {
      const res = await runPipeline.mutateAsync({ handoverId, fromStage });
      setActiveJobId(res.id);
      sessionStorage.setItem(`relayops-job-${handoverId}`, res.id);
      setElapsedSeconds(0);
      setLogs([]);
    } catch {
      // Handled by toast
    }
  };

  // Handler to retry pipeline
  const handleRetryPipeline = async () => {
    if (!activeJobId) return;
    try {
      const res = await retryPipeline.mutateAsync({
        jobId: activeJobId,
        fromStage: selectedRetryStage,
      });
      setActiveJobId(res.id);
      sessionStorage.setItem(`relayops-job-${handoverId}`, res.id);
    } catch {
      // Handled by toast
    }
  };

  const currentStageId = job?.stage || (job?.status === "done" ? "snapshot_v1" : "connect_check");
  const currentStageIndex = PIPELINE_STAGES.findIndex((s) => s.id === currentStageId);
  const isDone = job?.status === "done";
  const isFailed = job?.status === "failed";
  const isRunning = job?.status === "running" || job?.status === "queued";

  const formatElapsed = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const secs = sec % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  if (handoverLoading || !handover) {
    return (
      <div className="space-y-6">
        <PageHeader title="Loading Handover Pipeline..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Knowledge Pipeline Orchestrator"
        description={`Traceable pipeline execution for ${handover.notes || "PayFlow Handover"}.`}
        breadcrumbs={[
          { label: "Handovers", href: "/handovers" },
          { label: `Handover ${handover.id}`, href: `/handovers/${handover.id}` },
          { label: "Pipeline" },
        ]}
        actions={
          <div className="flex items-center gap-2">
            {!activeJobId && (
              <Button
                size="sm"
                onClick={() => handleStartPipeline()}
                disabled={runPipeline.isPending}
                className="gap-1.5 text-xs"
              >
                {runPipeline.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Play className="h-3.5 w-3.5" />
                )}
                Start Full Pipeline
              </Button>
            )}
            {isDone && (
              <Button
                size="sm"
                onClick={() => navigate(`/handovers/${handover.id}/review`)}
                className="gap-1.5 text-xs bg-verified text-primary-foreground hover:bg-verified/90"
              >
                <span>Start Review</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        }
      />

      {/* Top Status Banner */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] text-muted-foreground uppercase font-semibold">
                Pipeline Status
              </p>
              <div className="mt-1 flex items-center gap-2">
                <StatusBadge
                  status={
                    isDone
                      ? "verified"
                      : isFailed
                        ? "conflict"
                        : isRunning
                          ? "needs_review"
                          : "draft"
                  }
                  size="sm"
                />
              </div>
            </div>
            {isRunning && <Loader2 className="h-5 w-5 animate-spin text-primary" />}
            {isDone && <CheckCircle2 className="h-5 w-5 text-verified" />}
            {isFailed && <AlertCircle className="h-5 w-5 text-conflict" />}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] text-muted-foreground uppercase font-semibold">
                Execution Time
              </p>
              <div className="mt-1 flex items-center gap-1.5 font-mono text-base font-bold text-foreground">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <span>{formatElapsed(elapsedSeconds)}</span>
              </div>
            </div>
            <span className="font-mono text-xs text-muted-foreground">
              {job?.progress ?? 0}% completed
            </span>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] text-muted-foreground uppercase font-semibold">
                Active Job ID
              </p>
              <p className="mt-1 font-mono text-xs font-semibold text-foreground">
                {activeJobId ?? "No active job"}
              </p>
            </div>
            {activeJobId && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => void refetchJob()}
                className="h-7 w-7 text-muted-foreground"
                aria-label="Refresh job status"
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </Button>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Main Pipeline Layout: Vertical Stepper & Live Log Terminal */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left: 11-Stage Vertical Stepper */}
        <Card className="lg:col-span-7">
          <CardHeader className="pb-3 border-b">
            <CardTitle className="text-sm font-semibold">
              Pipeline Stage Progress (11 Stages)
            </CardTitle>
            <CardDescription className="text-xs">
              Idempotent stages verifying evidence, building the entity graph, and resolving
              contradictions.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-5">
            <div className="relative space-y-4">
              {PIPELINE_STAGES.map((stg, idx) => {
                const isStageComplete =
                  isDone ||
                  (currentStageIndex > idx && !isFailed) ||
                  (isDone && idx <= currentStageIndex);
                const isStageActive =
                  isRunning &&
                  (currentStageIndex === idx || (currentStageIndex === -1 && idx === 0));
                const isStageFailed = isFailed && currentStageIndex === idx;

                return (
                  <div key={stg.id} className="relative flex items-start gap-3.5 group">
                    {/* Vertical linking line */}
                    {idx < PIPELINE_STAGES.length - 1 && (
                      <div
                        className={cn(
                          "absolute left-4 top-8 -bottom-4 w-0.5 transition-colors",
                          isStageComplete ? "bg-verified/60" : "bg-border",
                        )}
                      />
                    )}

                    {/* Step Icon Indicator */}
                    <div
                      className={cn(
                        "relative z-10 flex size-8 shrink-0 items-center justify-center rounded-full border text-xs font-mono font-bold transition-all",
                        isStageComplete && "border-verified bg-verified text-primary-foreground",
                        isStageActive &&
                          "border-primary bg-primary/10 text-primary ring-4 ring-primary/20 animate-pulse",
                        isStageFailed && "border-conflict bg-conflict text-primary-foreground",
                        !isStageComplete &&
                          !isStageActive &&
                          !isStageFailed &&
                          "border-border bg-muted text-muted-foreground",
                      )}
                    >
                      {isStageComplete ? (
                        <CheckCircle2 className="size-4" />
                      ) : isStageActive ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : isStageFailed ? (
                        <AlertCircle className="size-4" />
                      ) : (
                        idx + 1
                      )}
                    </div>

                    {/* Stage Details */}
                    <div className="flex-1 space-y-0.5 pt-0.5">
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={cn(
                            "text-xs font-semibold",
                            isStageActive && "text-primary",
                            isStageComplete && "text-foreground",
                            isStageFailed && "text-conflict",
                          )}
                        >
                          {stg.label}
                        </span>

                        {isStageActive && (
                          <Badge
                            variant="outline"
                            className="border-primary/40 text-primary text-[10px] animate-pulse"
                          >
                            Processing
                          </Badge>
                        )}
                        {isStageComplete && (
                          <span className="font-mono text-[10px] text-verified">Done</span>
                        )}
                      </div>
                      <p className="text-[11px] text-muted-foreground leading-relaxed">
                        {stg.description}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Failure Box & Retry From Stage Trigger */}
            {isFailed && (
              <div className="mt-6 rounded-lg border border-conflict/30 bg-conflict/5 p-4 space-y-3">
                <div className="flex items-start gap-2.5">
                  <AlertCircle className="h-4 w-4 shrink-0 text-conflict mt-0.5" />
                  <div className="space-y-1">
                    <p className="text-xs font-semibold text-conflict">
                      Pipeline Execution Interrupted
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {job?.error ||
                        "An error occurred during stage execution. Earlier stage outputs were preserved."}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-2 border-t border-conflict/20">
                  <span className="text-xs text-muted-foreground">Resume from stage:</span>
                  <Select value={selectedRetryStage} onValueChange={setSelectedRetryStage}>
                    <SelectTrigger className="h-8 text-xs w-48">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PIPELINE_STAGES.map((s) => (
                        <SelectItem key={s.id} value={s.id} className="text-xs">
                          {s.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    size="sm"
                    onClick={handleRetryPipeline}
                    disabled={retryPipeline.isPending}
                    className="h-8 gap-1 text-xs"
                  >
                    <RefreshCw className="h-3 w-3" />
                    Retry
                  </Button>
                </div>
              </div>
            )}

            {/* Completion Success Card */}
            {isDone && (
              <div className="mt-6 rounded-lg border border-verified/30 bg-verified/5 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-verified" />
                    <div>
                      <p className="text-xs font-semibold text-foreground">
                        Handover Pipeline Completed Successfully
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        All claims bound to valid evidence citations. Snapshot v1 frozen.
                      </p>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => navigate(`/handovers/${handover.id}/review`)}
                    className="gap-1.5 text-xs bg-verified text-primary-foreground hover:bg-verified/90"
                  >
                    <span>Start Review</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right: Live Terminal & Execution Logs */}
        <Card className="lg:col-span-5 flex flex-col">
          <CardHeader className="pb-3 border-b flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              <Terminal className="h-4 w-4 text-primary" />
              <CardTitle className="text-xs font-semibold">Live Pipeline Stream</CardTitle>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setLogsExpanded(!logsExpanded)}
              className="h-6 w-6 text-muted-foreground"
              aria-label="Toggle terminal logs"
            >
              {logsExpanded ? (
                <ChevronDown className="h-3.5 w-3.5" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5" />
              )}
            </Button>
          </CardHeader>
          <CardContent className="flex-1 p-0">
            {logsExpanded && (
              <div className="h-[480px] overflow-y-auto bg-black/95 p-3.5 font-mono text-[11px] leading-relaxed text-slate-300">
                {logs.length > 0 ? (
                  logs.map((log, i) => (
                    <div key={`${log.ts}-${i}`} className="flex gap-2 py-0.5">
                      <span className="text-slate-500 select-none shrink-0">
                        {log.ts ? log.ts.substring(11, 19) : "--:--:--"}
                      </span>
                      <span className="text-emerald-400 select-none shrink-0">&gt;</span>
                      <span className="break-all">{log.message}</span>
                    </div>
                  ))
                ) : (
                  <div className="flex h-full items-center justify-center text-slate-500 italic">
                    Waiting for pipeline events...
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
