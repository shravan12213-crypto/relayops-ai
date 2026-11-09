import * as React from "react";
import { Ban, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";

export interface RejectClaimModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  claimId?: string;
  claimText?: string;
  onReject?: (reason: string) => Promise<void> | void;
  onConfirm?: (reason: string) => Promise<void> | void;
  isLoading?: boolean;
}

const COMMON_REASONS = [
  "Insufficient source evidence",
  "Contradicts latest merged code / ADR",
  "Outdated architecture decision",
  "Internal / sensitive details omitted",
];

export function RejectClaimModal({
  open,
  onOpenChange,
  claimText,
  onReject,
  onConfirm,
  isLoading = false,
}: RejectClaimModalProps) {
  const [reason, setReason] = React.useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) return;
    if (onConfirm) {
      await onConfirm(reason.trim());
    } else if (onReject) {
      await onReject(reason.trim());
    }
    onOpenChange(false);
    setReason("");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <span className="grid size-7 place-items-center rounded-md bg-destructive/10 text-destructive">
              <Ban className="h-4 w-4" />
            </span>
            <DialogTitle className="text-base font-semibold">Reject Candidate Claim</DialogTitle>
          </div>
          <DialogDescription className="text-xs">
            A reason is required to reject a claim. This will be preserved in the audit ledger and
            excluded from successor-facing views.
          </DialogDescription>
        </DialogHeader>

        {claimText && (
          <div className="rounded bg-muted/40 p-2.5 text-xs text-muted-foreground border line-clamp-2 italic">
            "{claimText}"
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3 pt-2">
          {/* Quick chips */}
          <div className="space-y-1.5">
            <span className="text-[11px] text-muted-foreground font-medium">Quick Reasons:</span>
            <div className="flex flex-wrap gap-1.5">
              {COMMON_REASONS.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setReason(r)}
                  className="rounded-full border border-border/80 bg-muted/40 px-2 py-0.5 text-[10px] text-muted-foreground hover:border-primary hover:text-foreground transition-colors"
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1">
            <label htmlFor="reject-reason" className="text-xs font-medium text-foreground">
              Rejection Reason Note *
            </label>
            <Textarea
              id="reject-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Explain why this claim is invalid or rejected..."
              rows={3}
              className="text-xs resize-none"
              required
            />
          </div>

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onOpenChange(false)}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="destructive"
              size="sm"
              disabled={isLoading || !reason.trim()}
              className="gap-1.5 text-xs"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Rejecting...
                </>
              ) : (
                <>
                  <Ban className="h-3.5 w-3.5" />
                  Confirm Rejection
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export const RejectClaimPopover = RejectClaimModal;
