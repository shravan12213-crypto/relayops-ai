import * as React from "react";
import { Check, Edit3, X, History, Sparkles, User, ShieldAlert, ArrowRight, Save } from "lucide-react";

import { ConfidenceMeter } from "@/components/review/ConfidenceMeter";
import { RejectClaimPopover } from "@/components/review/RejectClaimPopover";
import { WordDiff } from "@/components/review/WordDiff";
import { CitationPill } from "@/components/shared/CitationPill";
import { SensitivityBadge } from "@/components/shared/SensitivityBadge";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { type Claim, type EvidenceRef } from "@/lib/api/review";
import { cn } from "@/lib/utils";

export interface ReviewClaimCardProps {
  claim: Claim;
  isSelected: boolean;
  isEditing: boolean;
  onSelect: () => void;
  onAccept: (claim: Claim) => void;
  onReject: (claim: Claim, reason: string) => void;
  onSaveEdit: (claim: Claim, newText: string) => void;
  onCancelEdit: () => void;
  onStartEdit: () => void;
  onSelectEvidence: (evidence: EvidenceRef) => void;
  onJumpToClaim?: (claimId: string) => void;
  concurrencyConflict?: boolean;
}

export function ReviewClaimCard({
  claim,
  isSelected,
  isEditing,
  onSelect,
  onAccept,
  onReject,
  onSaveEdit,
  onCancelEdit,
  onStartEdit,
  onSelectEvidence,
  onJumpToClaim,
  concurrencyConflict = false,
}: ReviewClaimCardProps) {
  const [editText, setEditText] = React.useState(claim.text);
  const [showDiff, setShowDiff] = React.useState(false);
  const [rejectOpen, setRejectOpen] = React.useState(false);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  // Sync edit text when claim changes externally
  React.useEffect(() => {
    setEditText(claim.text);
  }, [claim.text]);

  // Focus textarea when editing begins
  React.useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.setSelectionRange(
        textareaRef.current.value.length,
        textareaRef.current.value.length,
      );
    }
  }, [isEditing]);

  const handleSave = () => {
    if (editText.trim() && editText !== claim.text) {
      onSaveEdit(claim, editText.trim());
    } else {
      onCancelEdit();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSave();
    } else if (e.key === "Escape") {
      e.preventDefault();
      setEditText(claim.text);
      onCancelEdit();
    }
  };

  // Determine origin display
  const getOriginInfo = () => {
    switch (claim.origin) {
      case "human":
        return {
          icon: User,
          label: claim.edited_by ? `Human (${claim.edited_by})` : "Human-asserted",
          className: "bg-canvas-2 text-ink-muted border-brand",
        };
      case "rule":
        return {
          icon: History,
          label: "Rule-derived",
          className: "bg-canvas-2 text-ink-muted border-card-border",
        };
      case "llm":
      default:
        return {
          icon: Sparkles,
          label: "AI-extracted",
          className: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
        };
    }
  };

  const originInfo = getOriginInfo();
  const OriginIcon = originInfo.icon;

  // Check if superseded
  const supersededId = claim.rejected_reason?.startsWith("superseded by claim ")
    ? claim.rejected_reason.replace("superseded by claim ", "").trim()
    : null;

  return (
    <div
      onClick={onSelect}
      className={cn(
        "group relative rounded-2xl border bg-card p-4 transition-all duration-150",
        isSelected
          ? "border-brand shadow-sm ring-2 ring-primary/20"
          : "border-card-border hover:border-card-border hover:shadow-xs",
        claim.status === "rejected" && "opacity-60 bg-canvas-2",
      )}
    >
      {/* Concurrency conflict banner */}
      {concurrencyConflict && (
        <div className="mb-3 flex items-center gap-2 rounded-md bg-warn-soft border border-needs-review px-3 py-2 text-xs text-needs-review dark:text-needs-review">
          <ShieldAlert className="h-4 w-4 shrink-0" />
          <span>
            <strong>Concurrent Update:</strong> This claim was modified by another reviewer.
            Review changes before saving.
          </span>
        </div>
      )}

      {/* Superseded Ribbon */}
      {supersededId && (
        <div className="mb-2.5 flex items-center gap-1.5 rounded-md bg-danger-soft border border-conflict/20 px-2.5 py-1 text-xs text-conflict dark:text-conflict font-medium">
          <span>Superseded by newer decision:</span>
          {onJumpToClaim ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onJumpToClaim(supersededId);
              }}
              className="inline-flex items-center gap-1 underline underline-offset-2 hover:text-conflict dark:hover:text-conflict"
            >
              claim {supersededId.slice(0, 8)}...
              <ArrowRight className="h-3 w-3" />
            </button>
          ) : (
            <span className="font-mono text-[11px]">{supersededId.slice(0, 8)}</span>
          )}
        </div>
      )}

      {/* Header bar: badges */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <StatusBadge status={claim.status} size="sm" />
          <ConfidenceMeter confidence={claim.confidence} />
          <SensitivityBadge level={claim.sensitivity} />

          {/* Kind badge */}
          <span className="rounded bg-canvas-2 px-1.5 py-0.5 font-mono text-[10px] text-ink-muted uppercase tracking-wide">
            {claim.kind.replace(/_/g, " ")}
          </span>

          {/* Origin badge */}
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium",
              originInfo.className,
            )}
          >
            <OriginIcon className="h-2.5 w-2.5" />
            {originInfo.label}
          </span>
        </div>

        {/* Claim ID hint */}
        <span className="font-mono text-[10px] text-ink-faint">
          #{claim.id.slice(0, 8)}
        </span>
      </div>

      {/* Main content area */}
      <div className="mt-3">
        {isEditing ? (
          <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
            <Textarea
              ref={textareaRef}
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={3}
              className="w-full resize-y font-sans text-sm leading-relaxed border-brand focus-visible:ring-1"
              placeholder="Edit claim text..."
            />
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-ink-muted">
                <kbd className="rounded border bg-canvas-2 px-1 text-[10px]">Ctrl+Enter</kbd> to save,{" "}
                <kbd className="rounded border bg-canvas-2 px-1 text-[10px]">Esc</kbd> to cancel
              </span>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs"
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditText(claim.text);
                    onCancelEdit();
                  }}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  className="h-7 text-xs gap-1"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSave();
                  }}
                >
                  <Save className="h-3 w-3" />
                  Save Edit
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div>
            <p className="text-sm font-medium leading-relaxed text-ink select-text break-words">
              {claim.text}
            </p>

            {/* Word diff toggle for edited claims */}
            {claim.status === "edited" && (
              <div className="mt-2" onClick={(e) => e.stopPropagation()}>
                <button
                  type="button"
                  onClick={() => setShowDiff((v) => !v)}
                  className="text-xs text-brand-text underline underline-offset-2 hover:text-brand-text/80"
                >
                  {showDiff ? "Hide edits diff" : "Show diff vs AI extracted draft"}
                </button>
                {showDiff && (
                  <div className="mt-2">
                    <WordDiff
                      originalText={claim.text}
                      editedText={claim.text}
                    />
                  </div>
                )}
              </div>
            )}

            {/* Rejection reason note if rejected */}
            {claim.status === "rejected" && claim.rejected_reason && (
              <div className="mt-2 rounded bg-canvas-2 px-2 py-1 text-xs text-ink-muted italic">
                Reason: {claim.rejected_reason}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Citations row */}
      {claim.evidence && claim.evidence.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5 pt-2 border-t border-card-border">
          <span className="text-[11px] font-medium text-ink-muted">Evidence:</span>
          {claim.evidence.map((ev, idx) => (
            <CitationPill
              key={`${ev.artifact_id}-${idx}`}
              artifactId={ev.artifact_id}
              sourceUri={ev.source_uri}
              snippet={ev.snippet}
              sourceType={ev.source_type}
              onClickSnippet={() => onSelectEvidence(ev)}
            />
          ))}
        </div>
      )}

      {/* Footer action bar */}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-card-border text-xs">
        <div className="flex items-center gap-1.5 text-ink-muted min-w-0">
          <span className="capitalize">{claim.section}</span>
          <span>•</span>
          <span className="font-mono text-[11px]">order #{claim.order_index}</span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
          <TooltipProvider delayDuration={300}>
            {/* Accept button */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="sm"
                  variant={claim.status === "accepted" ? "default" : "outline"}
                  className={cn(
                    "h-7 px-2.5 text-xs gap-1 font-medium",
                    claim.status === "accepted" && "bg-verified hover:bg-verified/90 text-white",
                  )}
                  onClick={() => onAccept(claim)}
                >
                  <Check className="h-3 w-3" />
                  Accept
                  <kbd className="ml-1 hidden sm:inline-block font-mono text-[9px] opacity-70">a</kbd>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="top">Accept claim into handover (Key: a)</TooltipContent>
            </Tooltip>

            {/* Edit button */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="sm"
                  variant={claim.status === "edited" ? "default" : "outline"}
                  className="h-7 px-2.5 text-xs gap-1"
                  onClick={() => (isEditing ? onCancelEdit() : onStartEdit())}
                >
                  <Edit3 className="h-3 w-3" />
                  Edit
                  <kbd className="ml-1 hidden sm:inline-block font-mono text-[9px] opacity-70">e</kbd>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="top">Edit claim text (Key: e)</TooltipContent>
            </Tooltip>

            {/* Reject button */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="sm"
                  variant={claim.status === "rejected" ? "destructive" : "outline"}
                  className="h-7 px-2.5 text-xs gap-1 hover:border-destructive/40 hover:text-destructive"
                  onClick={() => setRejectOpen(true)}
                >
                  <X className="h-3 w-3" />
                  Reject
                  <kbd className="ml-1 hidden sm:inline-block font-mono text-[9px] opacity-70">x</kbd>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="top">Reject claim with required reason (Key: x)</TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {/* Reject Popover/Modal */}
          <RejectClaimPopover
            open={rejectOpen}
            onOpenChange={setRejectOpen}
            claimText={claim.text}
            onConfirm={(reason: string) => {
              onReject(claim, reason);
              setRejectOpen(false);
            }}
          />
        </div>
      </div>
    </div>
  );
}
