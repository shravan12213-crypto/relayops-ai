import * as React from "react";
import { AlertCircle, AlertTriangle, Check, CheckCircle2, ShieldAlert } from "lucide-react";

import { EmptyState } from "@/components/shared/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/lib/api/auth";
import {
  useAmbiguities,
  useResolveAmbiguity,
  useWaiveAmbiguity,
  type Ambiguity,
} from "@/lib/api/review";
import { cn } from "@/lib/utils";

export interface AmbiguitiesTabProps {
  handoverId: string;
}

export function AmbiguitiesTab({ handoverId }: AmbiguitiesTabProps) {
  const { user } = useAuth();
  const { data: ambiguities = [] } = useAmbiguities(handoverId);
  const resolveMutation = useResolveAmbiguity(handoverId);
  const waiveMutation = useWaiveAmbiguity(handoverId);

  const [activeTab, setActiveTab] = React.useState<"open" | "resolved">("open");
  const [selectedAmbiguity, setSelectedAmbiguity] = React.useState<Ambiguity | null>(null);
  const [actionType, setActionType] = React.useState<"resolve" | "waive" | null>(null);
  const [actionNote, setActionNote] = React.useState("");

  const isLead = user?.role === "lead";

  const openAmbiguities = ambiguities.filter((a) => a.status === "open");
  const resolvedAmbiguities = ambiguities.filter(
    (a) => a.status === "resolved" || a.status === "waived",
  );

  const displayList = activeTab === "open" ? openAmbiguities : resolvedAmbiguities;

  const handleOpenAction = (amb: Ambiguity, type: "resolve" | "waive") => {
    setSelectedAmbiguity(amb);
    setActionType(type);
    setActionNote("");
  };

  const handleConfirmAction = async () => {
    if (!selectedAmbiguity || !actionType || !actionNote.trim()) return;

    if (actionType === "resolve") {
      await resolveMutation.mutateAsync({
        ambiguityId: selectedAmbiguity.id,
        resolution_note: actionNote.trim(),
      });
    } else if (actionType === "waive") {
      await waiveMutation.mutateAsync({
        ambiguityId: selectedAmbiguity.id,
        waiver_reason: actionNote.trim(),
      });
    }

    setSelectedAmbiguity(null);
    setActionType(null);
    setActionNote("");
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity.toLowerCase()) {
      case "high":
        return (
          <Badge variant="outline" className="border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-400 gap-1 text-[10px]">
            <AlertCircle className="h-2.5 w-2.5" />
            High Severity
          </Badge>
        );
      case "medium":
        return (
          <Badge variant="outline" className="border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400 gap-1 text-[10px]">
            <AlertTriangle className="h-2.5 w-2.5" />
            Medium
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" className="border-slate-500/30 bg-slate-500/10 text-slate-600 dark:text-slate-400 text-[10px]">
            Low
          </Badge>
        );
    }
  };

  return (
    <div className="flex h-full flex-col p-4 space-y-3">
      {/* Subnav: Open vs Resolved */}
      <div className="flex items-center justify-between border-b border-border/60 pb-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveTab("open")}
            className={cn(
              "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              activeTab === "open"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            Open Issues ({openAmbiguities.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("resolved")}
            className={cn(
              "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              activeTab === "resolved"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            Resolved ({resolvedAmbiguities.length})
          </button>
        </div>

        <span className="text-[11px] text-muted-foreground">
          Rule: Never smooth over gaps
        </span>
      </div>

      {/* Ambiguity Cards List */}
      <ScrollArea className="flex-1 -mr-2 pr-2">
        {displayList.length === 0 ? (
          <div className="py-12">
            <EmptyState
              icon={CheckCircle2}
              title={activeTab === "open" ? "Zero Open Ambiguities" : "No Resolved Issues Yet"}
              description={
                activeTab === "open"
                  ? "All detected evidence gaps and contradictions have been addressed."
                  : "Resolved or waived ambiguity ledger items will appear here."
              }
            />
          </div>
        ) : (
          <div className="space-y-3">
            {displayList.map((amb) => (
              <div
                key={amb.id}
                className="rounded-lg border border-border/80 bg-card p-3 shadow-2xs space-y-2 transition-colors hover:border-border"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {getSeverityBadge(amb.severity)}
                      <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground uppercase">
                        {amb.type}
                      </span>
                      {amb.status !== "open" && (
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[10px]",
                            amb.status === "resolved"
                              ? "border-verified/30 text-verified bg-verified/10"
                              : "border-slate-500/30 text-muted-foreground",
                          )}
                        >
                          {amb.status}
                        </Badge>
                      )}
                    </div>
                    <h4 className="text-xs font-semibold text-foreground leading-snug">
                      {amb.title}
                    </h4>
                  </div>
                </div>

                {amb.description && (
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {amb.description}
                  </p>
                )}

                {amb.resolution_note && (
                  <div className="rounded bg-muted/60 p-2 text-xs text-foreground space-y-0.5 border-l-2 border-primary">
                    <span className="text-[10px] font-semibold text-muted-foreground uppercase">
                      Resolution Note:
                    </span>
                    <p>{amb.resolution_note}</p>
                  </div>
                )}

                {/* Actions for Open Ambiguities */}
                {amb.status === "open" && (
                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-border/40">
                    {isLead && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-6 text-xs text-muted-foreground hover:text-foreground"
                        onClick={() => handleOpenAction(amb, "waive")}
                      >
                        Waive (Lead)
                      </Button>
                    )}
                    <Button
                      size="sm"
                      className="h-6 text-xs gap-1"
                      onClick={() => handleOpenAction(amb, "resolve")}
                    >
                      <Check className="h-3 w-3" />
                      Resolve
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </ScrollArea>

      {/* Resolve / Waive Note Dialog */}
      <Dialog
        open={Boolean(selectedAmbiguity && actionType)}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedAmbiguity(null);
            setActionType(null);
          }
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base flex items-center gap-2">
              {actionType === "resolve" ? (
                <>
                  <CheckCircle2 className="h-4 w-4 text-verified" />
                  <span>Resolve Ambiguity</span>
                </>
              ) : (
                <>
                  <ShieldAlert className="h-4 w-4 text-amber-500" />
                  <span>Waive Ambiguity (Project Lead)</span>
                </>
              )}
            </DialogTitle>
            <DialogDescription className="text-xs">
              {actionType === "resolve"
                ? "Document the verified conclusion or resolution before marking this ambiguity as resolved."
                : "Provide a justification for why this gap or conflict is safe to waive for this handover."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2">
            <div className="rounded bg-muted/50 p-2 text-xs">
              <strong>Item:</strong> {selectedAmbiguity?.title}
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-foreground">
                {actionType === "resolve" ? "Resolution Note *" : "Waiver Justification *"}
              </label>
              <Textarea
                value={actionNote}
                onChange={(e) => setActionNote(e.target.value)}
                rows={3}
                placeholder={
                  actionType === "resolve"
                    ? "e.g., Verified with team that rate limit was increased to 500/min in PR #104."
                    : "e.g., Low operational risk, scheduled for post-handover refactor."
                }
                className="text-xs"
              />
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setSelectedAmbiguity(null);
                setActionType(null);
              }}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!actionNote.trim() || resolveMutation.isPending || waiveMutation.isPending}
              onClick={handleConfirmAction}
            >
              {actionType === "resolve" ? "Save Resolution" : "Confirm Waiver"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
