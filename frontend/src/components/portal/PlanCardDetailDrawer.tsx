import { Calendar, CheckCircle2, Circle, Clock, Flame, Tag, User } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  useUpdatePlanItem,
  type PlanItemWithClaims,
} from "@/lib/api/portal";

interface PlanCardDetailDrawerProps {
  item: PlanItemWithClaims | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  handoverId: string;
}

const BUCKET_TITLES: Record<string, string> = {
  d1_7: "Day 1-7 (First Week Triage)",
  d8_14: "Day 8-14 (Deep Dive & Independence)",
  d15_30: "Day 15-30 (Autonomous Ownership)",
};

export function PlanCardDetailDrawer({
  item,
  open,
  onOpenChange,
  handoverId,
}: PlanCardDetailDrawerProps) {
  const updateMutation = useUpdatePlanItem(handoverId);

  if (!item) return null;

  const handleStatusChange = (newStatus: "todo" | "doing" | "done") => {
    updateMutation.mutate({
      itemId: item.id,
      data: { status: newStatus },
    });
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-md space-y-5 overflow-y-auto">
        <SheetHeader className="space-y-2 border-b pb-4 text-left">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge
              variant="outline"
              className={`text-[10px] uppercase font-semibold ${
                item.priority === "high"
                  ? "border-red-500/30 text-red-500 bg-red-500/10"
                  : item.priority === "med" || item.priority === "medium"
                    ? "border-needs-review text-needs-review bg-warn-soft"
                    : "border-brand text-ink-muted bg-canvas-2"
              }`}
            >
              <Flame className="h-3 w-3 mr-1" />
              {item.priority} priority
            </Badge>
            <Badge variant="secondary" className="text-[10px]">
              <Calendar className="h-3 w-3 mr-1" />
              {BUCKET_TITLES[item.day_bucket] ?? item.day_bucket}
            </Badge>
          </div>
          <SheetTitle className="text-base font-semibold leading-snug text-ink">
            {item.title}
          </SheetTitle>
          <SheetDescription className="text-xs text-ink-muted">
            Task ID: <span className="font-mono">{item.id}</span>
          </SheetDescription>
        </SheetHeader>

        {/* Status switcher */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-ink-muted">Status</label>
          <div className="grid grid-cols-3 gap-2">
            <Button
              type="button"
              size="sm"
              variant={item.status === "todo" ? "default" : "outline"}
              onClick={() => handleStatusChange("todo")}
              className="text-xs gap-1.5 h-8"
            >
              <Circle className="h-3 w-3" />
              To Do
            </Button>
            <Button
              type="button"
              size="sm"
              variant={item.status === "doing" ? "default" : "outline"}
              onClick={() => handleStatusChange("doing")}
              className="text-xs gap-1.5 h-8 text-needs-review"
            >
              <Clock className="h-3 w-3" />
              In Progress
            </Button>
            <Button
              type="button"
              size="sm"
              variant={item.status === "done" ? "default" : "outline"}
              onClick={() => handleStatusChange("done")}
              className="text-xs gap-1.5 h-8 text-verified"
            >
              <CheckCircle2 className="h-3 w-3" />
              Done
            </Button>
          </div>
        </div>

        {/* Task description */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-ink-muted">Description & Plan</label>
          <div className="rounded-lg border bg-canvas-2 p-3 text-xs leading-relaxed text-ink">
            {item.description || "No specific instructions specified."}
          </div>
        </div>

        {/* Assignee if any */}
        {item.assignee && (
          <div className="flex items-center gap-2 text-xs text-ink-muted">
            <User className="h-3.5 w-3.5 text-brand-text" />
            <span>
              Assigned to: <strong className="text-ink">{item.assignee}</strong>
            </span>
          </div>
        )}

        {/* Grounded Linked Claims */}
        <div className="space-y-2 border-t pt-4">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-ink flex items-center gap-1.5">
              <Tag className="h-3.5 w-3.5 text-brand-text" />
              Grounded Claims ({item.linked_claims?.length ?? 0})
            </label>
          </div>

          {item.linked_claims && item.linked_claims.length > 0 ? (
            <div className="space-y-2.5">
              {item.linked_claims.map((claim) => (
                <div
                  key={claim.id}
                  className="space-y-1.5 rounded-lg border border-card-border bg-card p-3 text-xs"
                >
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant="outline" className="text-[10px] capitalize">
                      {claim.section} · {claim.kind.replace("_", " ")}
                    </Badge>
                    <Badge variant="secondary" className="text-[9px]">
                      {claim.status}
                    </Badge>
                  </div>
                  <p className="text-xs leading-relaxed text-ink">{claim.text}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-ink-muted italic">
              No specific claims linked to this task.
            </p>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
