import * as React from "react";
import { CheckCircle2, Loader2 } from "lucide-react";

import { useAcknowledgeReceipt } from "@/lib/api/portal";
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

interface SectionAcknowledgementDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  handoverId: string;
  section: string;
  sectionTitle: string;
}

export function SectionAcknowledgementDialog({
  open,
  onOpenChange,
  handoverId,
  section,
  sectionTitle,
}: SectionAcknowledgementDialogProps) {
  const [note, setNote] = React.useState("");
  const acknowledgeMutation = useAcknowledgeReceipt(handoverId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await acknowledgeMutation.mutateAsync({
        section,
        comprehension_note: note.trim() || undefined,
      });
      onOpenChange(false);
      setNote("");
    } catch {
      // Toast handled by mutation hook
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit} className="space-y-4">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <div className="rounded-md bg-verified/10 p-1.5 text-verified">
                <CheckCircle2 className="h-4 w-4" />
              </div>
              <DialogTitle className="text-base font-semibold">
                Acknowledge Comprehension: {sectionTitle}
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs text-ink-muted">
              Confirm that you have read and understood the verified claims and runbooks in this
              section. This comprehension receipt will be timestamped and sealed in the handover
              audit record.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 text-xs">
            <label className="font-medium text-ink">
              Comprehension Note / Follow-up (Optional)
            </label>
            <Textarea
              placeholder="e.g. Verified local docker test runs; tested fallback token caching..."
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              className="text-xs resize-none"
            />
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
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
              size="sm"
              disabled={acknowledgeMutation.isPending}
              className="gap-1.5 text-xs bg-verified text-white hover:bg-verified/90"
            >
              {acknowledgeMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <CheckCircle2 className="h-3.5 w-3.5" />
              )}
              Confirm & Record Receipt
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
