import { GitCompare, Check, Scale, CheckCircle2, ArrowRight } from "lucide-react";

import { EmptyState } from "@/components/shared/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useConflicts, usePatchClaim, type ConflictItem } from "@/lib/api/review";
import { cn } from "@/lib/utils";

export interface ConflictsTabProps {
  handoverId: string;
  onJumpToClaim?: (claimId: string) => void;
}

export function ConflictsTab({ handoverId, onJumpToClaim }: ConflictsTabProps) {
  const { data: conflicts = [] } = useConflicts(handoverId);
  const patchClaim = usePatchClaim(handoverId);

  const handleAcceptResolution = async (conflict: ConflictItem) => {
    if (conflict.winner_claim_id && conflict.loser_claim_id) {
      // Accept winner
      await patchClaim.mutateAsync({
        claimId: conflict.winner_claim_id,
        patch: { status: "accepted" },
      });
      // Reject loser with note
      await patchClaim.mutateAsync({
        claimId: conflict.loser_claim_id,
        patch: {
          status: "rejected",
          rejected_reason: `superseded by claim ${conflict.winner_claim_id}`,
        },
      });
    } else if (conflict.claim_a_id && conflict.claim_b_id) {
      // Pick higher authority as winner
      const winnerId =
        conflict.claim_b_authority >= conflict.claim_a_authority
          ? conflict.claim_b_id
          : conflict.claim_a_id;
      const loserId =
        winnerId === conflict.claim_b_id ? conflict.claim_a_id : conflict.claim_b_id;

      await patchClaim.mutateAsync({
        claimId: winnerId,
        patch: { status: "accepted" },
      });
      await patchClaim.mutateAsync({
        claimId: loserId,
        patch: {
          status: "rejected",
          rejected_reason: `superseded by claim ${winnerId}`,
        },
      });
    }
  };

  const handleKeepBoth = async (conflict: ConflictItem) => {
    if (conflict.claim_a_id) {
      await patchClaim.mutateAsync({
        claimId: conflict.claim_a_id,
        patch: { status: "accepted" },
      });
    }
    if (conflict.claim_b_id) {
      await patchClaim.mutateAsync({
        claimId: conflict.claim_b_id,
        patch: { status: "accepted" },
      });
    }
  };

  const getAuthorityBadge = (authority: number) => {
    const pct = Math.round(authority * 100);
    return (
      <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
        <Scale className="h-2.5 w-2.5 text-primary" />
        Auth: {authority.toFixed(1)} ({pct}%)
      </span>
    );
  };

  if (conflicts.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <EmptyState
          icon={CheckCircle2}
          title="No Conflicts Detected"
          description="Deterministic rules and LLM validation found no pairwise contradictions or conflicting technical decisions."
        />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col p-4 space-y-3">
      <div className="flex items-center justify-between border-b border-border/60 pb-2">
        <div className="flex items-center gap-2">
          <GitCompare className="h-4 w-4 text-primary" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Contradiction & Authority Engine ({conflicts.length})
          </h3>
        </div>
        <span className="text-[11px] text-muted-foreground">
          Bi-temporal resolution
        </span>
      </div>

      <ScrollArea className="flex-1 -mr-2 pr-2">
        <div className="space-y-4">
          {conflicts.map((conf) => {
            const isSuperseded = conf.status === "superseded";

            return (
              <div
                key={conf.id}
                className="rounded-lg border border-border/80 bg-card p-3 shadow-2xs space-y-3"
              >
                {/* Title & Status */}
                <div className="flex items-center justify-between gap-2">
                  <div className="space-y-0.5">
                    <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground uppercase">
                      {conf.subject}
                    </span>
                    <h4 className="text-xs font-semibold text-foreground">{conf.title}</h4>
                  </div>
                  <Badge
                    variant="outline"
                    className={cn(
                      "text-[10px]",
                      isSuperseded
                        ? "border-primary/30 text-primary bg-primary/10"
                        : "border-rose-500/30 text-rose-600 bg-rose-500/10",
                    )}
                  >
                    {isSuperseded ? "Authority Superseded" : "Open Contradiction"}
                  </Badge>
                </div>

                {conf.description && (
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {conf.description}
                  </p>
                )}

                {/* Side-by-side comparison */}
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {/* Claim A */}
                  <div className="rounded-md border border-border/60 bg-muted/20 p-2.5 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase text-muted-foreground">
                        Source A {conf.claim_a_id === conf.loser_claim_id && "(Older)"}
                      </span>
                      {getAuthorityBadge(conf.claim_a_authority)}
                    </div>
                    <p className="font-medium text-foreground text-xs leading-relaxed">
                      {conf.claim_a_text || "Claim A reference"}
                    </p>
                    {onJumpToClaim && conf.claim_a_id && (
                      <button
                        type="button"
                        onClick={() => onJumpToClaim(conf.claim_a_id)}
                        className="text-[11px] text-primary hover:underline flex items-center gap-0.5"
                      >
                        Inspect claim <ArrowRight className="h-2.5 w-2.5" />
                      </button>
                    )}
                  </div>

                  {/* Claim B */}
                  <div className="rounded-md border border-border/60 bg-muted/20 p-2.5 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase text-muted-foreground">
                        Source B {conf.claim_b_id === conf.winner_claim_id && "(Newer Winner)"}
                      </span>
                      {getAuthorityBadge(conf.claim_b_authority)}
                    </div>
                    <p className="font-medium text-foreground text-xs leading-relaxed">
                      {conf.claim_b_text || "Claim B reference"}
                    </p>
                    {onJumpToClaim && conf.claim_b_id && (
                      <button
                        type="button"
                        onClick={() => onJumpToClaim(conf.claim_b_id)}
                        className="text-[11px] text-primary hover:underline flex items-center gap-0.5"
                      >
                        Inspect claim <ArrowRight className="h-2.5 w-2.5" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Resolution Summary / Actions */}
                <div className="flex items-center justify-between pt-2 border-t border-border/40 text-xs">
                  <span className="text-[11px] text-muted-foreground truncate max-w-[220px]">
                    {conf.chosen_resolution || "Higher authority & recency precedence"}
                  </span>

                  <div className="flex items-center gap-1.5">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-6 text-xs text-muted-foreground"
                      onClick={() => handleKeepBoth(conf)}
                    >
                      Keep Both
                    </Button>
                    <Button
                      size="sm"
                      className="h-6 text-xs gap-1"
                      onClick={() => handleAcceptResolution(conf)}
                    >
                      <Check className="h-3 w-3" />
                      Accept Resolution
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </ScrollArea>
    </div>
  );
}
