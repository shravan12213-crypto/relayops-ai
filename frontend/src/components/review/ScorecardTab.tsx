import { Gauge, ShieldCheck, Layers, AlertCircle, Sparkles } from "lucide-react";

import { useHandoverScorecard } from "@/lib/api/handovers";
import { type Claim } from "@/lib/api/review";
import { cn } from "@/lib/utils";

export interface ScorecardTabProps {
  handoverId: string;
  claims: Claim[];
}

export function ScorecardTab({ handoverId, claims }: ScorecardTabProps) {
  const { data: scorecard } = useHandoverScorecard(handoverId);

  // Compute live breakdown from current claims in view
  const totalClaims = claims.length;
  const verifiedClaims = claims.filter(
    (c) => c.evidence && c.evidence.length > 0 && c.status !== "rejected",
  ).length;
  const verifiedPct = totalClaims > 0 ? Math.round((verifiedClaims / totalClaims) * 100) : 0;

  const score = scorecard?.overall_score ?? scorecard?.readiness_score ?? verifiedPct;

  return (
    <div className="flex h-full flex-col p-4 space-y-4 overflow-y-auto">
      {/* Header with Readiness Gauge */}
      <div className="rounded-xl border border-card-border bg-card p-4 shadow-2xs space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">
              Handover Completeness
            </span>
            <h3 className="text-sm font-semibold text-ink">Readiness Scorecard</h3>
          </div>
          <Gauge className="h-5 w-5 text-brand-text" />
        </div>

        {/* Big Score Display */}
        <div className="flex items-center gap-4 pt-1">
          <div className="relative flex h-16 w-16 shrink-0 items-center justify-center">
            <svg className="h-full w-full -rotate-90 transform" viewBox="0 0 36 36">
              <path
                className="text-muted/30"
                strokeWidth="4"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                className={cn(
                  "transition-all duration-500",
                  score >= 80 ? "text-verified" : score >= 50 ? "text-needs-review" : "text-conflict",
                )}
                strokeDasharray={`${score}, 100`}
                strokeWidth="4"
                strokeLinecap="round"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            </svg>
            <span className="absolute text-base font-bold text-ink">{score}%</span>
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-1.5">
              <span
                className={cn(
                  "inline-block h-2 w-2 rounded-full",
                  score >= 80 ? "bg-verified" : score >= 50 ? "bg-needs-review" : "bg-conflict",
                )}
              />
              <span className="text-xs font-semibold text-ink">
                {score >= 80
                  ? "Ready for Dual Sign-off"
                  : score >= 50
                    ? "In Review — Attention Needed"
                    : "Early Reconstruct Stage"}
              </span>
            </div>
            <p className="text-xs text-ink-muted leading-snug">
              Weighted index of claim verification, module coverage, and unresolved contradictions.
            </p>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        {/* Verified Claims */}
        <div className="rounded-lg border border-card-border bg-card p-2.5 sm:p-3 shadow-2xs space-y-1 min-w-0">
          <div className="flex items-center justify-between text-ink-muted gap-1">
            <span className="text-[10px] font-semibold uppercase truncate">Evidence Backed</span>
            <ShieldCheck className="h-3.5 w-3.5 text-verified shrink-0" />
          </div>
          <div className="text-lg font-bold text-ink">
            {verifiedPct}%
          </div>
          <p className="text-[11px] text-ink-muted truncate">
            {verifiedClaims} of {totalClaims} claims
          </p>
        </div>

        {/* Modules Documented */}
        <div className="rounded-lg border border-card-border bg-card p-2.5 sm:p-3 shadow-2xs space-y-1 min-w-0">
          <div className="flex items-center justify-between text-ink-muted gap-1">
            <span className="text-[10px] font-semibold uppercase truncate">Module Coverage</span>
            <Layers className="h-3.5 w-3.5 text-brand-text shrink-0" />
          </div>
          <div className="text-lg font-bold text-ink">
            {Math.round(scorecard?.modules_documented_pct ?? 100)}%
          </div>
          <p className="text-[11px] text-ink-muted truncate">Components documented</p>
        </div>

        {/* Epistemic Avg */}
        <div className="rounded-lg border border-card-border bg-card p-2.5 sm:p-3 shadow-2xs space-y-1 min-w-0">
          <div className="flex items-center justify-between text-ink-muted gap-1">
            <span className="text-[10px] font-semibold uppercase truncate">Epistemic Avg</span>
            <Sparkles className="h-3.5 w-3.5 text-purple-500 shrink-0" />
          </div>
          <div className="text-lg font-bold text-ink">
            {((scorecard?.epistemic_confidence_avg ?? 0.85) * 100).toFixed(0)}%
          </div>
          <p className="text-[11px] text-ink-muted truncate">Average source trust</p>
        </div>

        {/* Open Ambiguities */}
        <div className="rounded-lg border border-card-border bg-card p-2.5 sm:p-3 shadow-2xs space-y-1 min-w-0">
          <div className="flex items-center justify-between text-ink-muted gap-1">
            <span className="text-[10px] font-semibold uppercase truncate">High Severity</span>
            <AlertCircle className="h-3.5 w-3.5 text-conflict shrink-0" />
          </div>
          <div className="text-lg font-bold text-ink">
            {scorecard?.open_ambiguities_by_severity?.high ?? 0}
          </div>
          <p className="text-[11px] text-ink-muted truncate">Open gap items</p>
        </div>
      </div>

      {/* Summary Narrative */}
      {scorecard?.summary && (
        <div className="rounded-lg border border-card-border bg-canvas-2 p-3 text-xs space-y-1 shadow-2xs">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">
            Auditor Summary
          </span>
          <p className="text-ink-muted leading-relaxed">{scorecard.summary}</p>
        </div>
      )}

      {/* Product Rules Notice */}
      <div className="rounded-lg border border-card-border bg-canvas-2 p-3 text-[11px] text-ink-muted space-y-1">
        <span className="font-semibold text-ink">Non-negotiable product rule:</span>
        <p>
          Every claim shown to a successor has ≥ 1 evidence link to a real artifact. Claims with zero
          valid evidence are never persisted as verified.
        </p>
      </div>
    </div>
  );
}
