import * as React from "react";
import { HelpCircle, Loader2, Send } from "lucide-react";

import { useCreateQuestion } from "@/lib/api/portal";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

interface AskQuestionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  handoverId: string;
  outgoingName?: string;
  initialTitle?: string;
  initialQuestion?: string;
  ambiguityId?: string;
  artifactIds?: string[];
}

export function AskQuestionDialog({
  open,
  onOpenChange,
  handoverId,
  outgoingName = "Outgoing Contributor",
  initialTitle = "",
  initialQuestion = "",
  ambiguityId,
  artifactIds = [],
}: AskQuestionDialogProps) {
  const [title, setTitle] = React.useState(initialTitle);
  const [question, setQuestion] = React.useState(initialQuestion);
  const createQuestion = useCreateQuestion(handoverId);

  React.useEffect(() => {
    if (open) {
      setTitle(initialTitle);
      setQuestion(initialQuestion);
    }
  }, [open, initialTitle, initialQuestion]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !question.trim()) return;

    try {
      await createQuestion.mutateAsync({
        title: title.trim(),
        question: question.trim(),
        ambiguity_id: ambiguityId,
        artifact_ids: artifactIds,
      });
      onOpenChange(false);
      setTitle("");
      setQuestion("");
    } catch {
      // Toast handled by hook
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <div className="rounded-md bg-brand-soft p-1.5 text-brand-text">
                <HelpCircle className="h-4 w-4" />
              </div>
              <DialogTitle className="text-base font-semibold">
                Ask {outgoingName}
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs text-ink-muted">
              Submit an open inquiry directly to the outgoing contributor. It will be recorded in
              the project ledger and prioritized on their dashboard.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2 text-xs">
            <div className="space-y-1">
              <label className="font-medium text-ink">Topic / Summary</label>
              <Input
                placeholder="e.g. Webhook retry limit clarification"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                className="text-xs"
              />
            </div>

            <div className="space-y-1">
              <label className="font-medium text-ink">Question Details</label>
              <Textarea
                placeholder="Provide context on what documentation or evidence is missing..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={4}
                required
                className="text-xs resize-none"
              />
            </div>
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
              disabled={createQuestion.isPending || !title.trim() || !question.trim()}
              className="gap-1.5 text-xs"
            >
              {createQuestion.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Send className="h-3.5 w-3.5" />
              )}
              Submit Inquiry
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
