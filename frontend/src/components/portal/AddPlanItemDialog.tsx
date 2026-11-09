import * as React from "react";
import { Loader2, Plus } from "lucide-react";

import { useCreatePlanItem } from "@/lib/api/portal";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

interface AddPlanItemDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  handoverId: string;
  defaultDayBucket?: string;
}

export function AddPlanItemDialog({
  open,
  onOpenChange,
  handoverId,
  defaultDayBucket = "d1_7",
}: AddPlanItemDialogProps) {
  const [title, setTitle] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [dayBucket, setDayBucket] = React.useState(defaultDayBucket);
  const [priority, setPriority] = React.useState("med");

  const createMutation = useCreatePlanItem(handoverId);

  React.useEffect(() => {
    if (open) {
      setDayBucket(defaultDayBucket);
    }
  }, [open, defaultDayBucket]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    try {
      await createMutation.mutateAsync({
        title: title.trim(),
        description: description.trim(),
        day_bucket: dayBucket,
        priority,
      });
      onOpenChange(false);
      setTitle("");
      setDescription("");
    } catch {
      // Toast handled by mutation hook
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit} className="space-y-4">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold">
              Add Task to 30-Day Plan
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Define an onboarding milestone or operational transfer task for the successor.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-1 text-xs">
            <div className="space-y-1">
              <label className="font-medium text-foreground">Task Title</label>
              <Input
                placeholder="e.g. Set up local Docker payment webhook simulation"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                className="text-xs"
              />
            </div>

            <div className="space-y-1">
              <label className="font-medium text-foreground">Description & Context</label>
              <Textarea
                placeholder="Describe setup commands, expectations, or tests to run..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                className="text-xs resize-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="font-medium text-foreground">Timeline Bucket</label>
                <Select value={dayBucket} onValueChange={setDayBucket}>
                  <SelectTrigger className="text-xs h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="text-xs">
                    <SelectItem value="d1_7">Day 1-7 (First Week)</SelectItem>
                    <SelectItem value="d8_14">Day 8-14 (Deep Dive)</SelectItem>
                    <SelectItem value="d15_30">Day 15-30 (Autonomous)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <label className="font-medium text-foreground">Priority</label>
                <Select value={priority} onValueChange={setPriority}>
                  <SelectTrigger className="text-xs h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="text-xs">
                    <SelectItem value="high">High Priority</SelectItem>
                    <SelectItem value="med">Medium Priority</SelectItem>
                    <SelectItem value="low">Low Priority</SelectItem>
                  </SelectContent>
                </Select>
              </div>
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
              disabled={createMutation.isPending || !title.trim()}
              className="gap-1.5 text-xs"
            >
              {createMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Plus className="h-3.5 w-3.5" />
              )}
              Add Task
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
