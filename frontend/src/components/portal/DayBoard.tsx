import * as React from "react";
import {
  Calendar,
  CheckCircle2,
  Clock,
  Flame,
  GripVertical,
  Plus,
  Tag,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  usePlanItems,
  useUpdatePlanItem,
  type PlanItemWithClaims,
} from "@/lib/api/portal";
import { AddPlanItemDialog } from "./AddPlanItemDialog";
import { PlanCardDetailDrawer } from "./PlanCardDetailDrawer";

interface DayBoardProps {
  handoverId: string;
}

interface ColumnConfig {
  id: "d1_7" | "d8_14" | "d15_30";
  title: string;
  subtitle: string;
  accent: string;
}

const COLUMNS: ColumnConfig[] = [
  {
    id: "d1_7",
    title: "Day 1-7",
    subtitle: "First week environment & triage",
    accent: "border-blue-500/40 text-blue-500",
  },
  {
    id: "d8_14",
    title: "Day 8-14",
    subtitle: "Deep dive & independent tasks",
    accent: "border-amber-500/40 text-amber-500",
  },
  {
    id: "d15_30",
    title: "Day 15-30",
    subtitle: "Full operational ownership",
    accent: "border-verified/40 text-verified",
  },
];

export function DayBoard({ handoverId }: DayBoardProps) {
  const { data: items } = usePlanItems(handoverId);
  const updateMutation = useUpdatePlanItem(handoverId);

  const [selectedItem, setSelectedItem] = React.useState<PlanItemWithClaims | null>(null);
  const [detailOpen, setDetailOpen] = React.useState(false);
  const [addDialogOpen, setAddDialogOpen] = React.useState(false);
  const [targetBucket, setTargetBucket] = React.useState("d1_7");
  const [dragOverCol, setDragOverCol] = React.useState<string | null>(null);

  const itemsList = items ?? [];

  const handleDragStart = (e: React.DragEvent, itemId: string) => {
    e.dataTransfer.setData("text/plain", itemId);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDrop = (e: React.DragEvent, colId: string) => {
    e.preventDefault();
    setDragOverCol(null);
    const itemId = e.dataTransfer.getData("text/plain");
    if (!itemId) return;

    const item = itemsList.find((i) => i.id === itemId);
    if (item && item.day_bucket !== colId) {
      updateMutation.mutate({
        itemId,
        data: { day_bucket: colId },
      });
    }
  };

  const handleStatusCycle = (e: React.MouseEvent, item: PlanItemWithClaims) => {
    e.stopPropagation();
    const nextStatus = item.status === "todo" ? "doing" : item.status === "doing" ? "done" : "todo";
    updateMutation.mutate({
      itemId: item.id,
      data: { status: nextStatus },
    });
  };

  return (
    <div className="space-y-4">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            <Calendar className="h-4 w-4 text-primary" />
            Day 1-30 Successor Execution Board
          </h2>
          <p className="text-xs text-muted-foreground">
            Structured roadmap for onboarding. Drag cards between buckets to reorganize timeline.
          </p>
        </div>

        <Button
          size="sm"
          onClick={() => {
            setTargetBucket("d1_7");
            setAddDialogOpen(true);
          }}
          className="gap-1.5 text-xs h-8"
        >
          <Plus className="h-3.5 w-3.5" />
          Add Custom Task
        </Button>
      </div>

      {/* 3 Columns */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {COLUMNS.map((col) => {
          const colItems = itemsList.filter((i) => i.day_bucket === col.id);
          const isDragOver = dragOverCol === col.id;

          return (
            <div
              key={col.id}
              onDragOver={(e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                if (dragOverCol !== col.id) setDragOverCol(col.id);
              }}
              onDragLeave={() => {
                if (dragOverCol === col.id) setDragOverCol(null);
              }}
              onDrop={(e) => handleDrop(e, col.id)}
              className={`flex flex-col rounded-xl border bg-card/60 p-3.5 transition-all min-h-[420px] ${
                isDragOver ? "border-primary ring-2 ring-primary/20 bg-primary/5" : "border-border"
              }`}
            >
              {/* Column Header */}
              <div className="flex items-center justify-between border-b pb-2.5 mb-3">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-foreground">{col.title}</span>
                    <Badge variant="secondary" className="text-[10px] h-5 px-1.5 font-mono">
                      {colItems.length}
                    </Badge>
                  </div>
                  <p className="text-[10px] text-muted-foreground">{col.subtitle}</p>
                </div>

                <Button
                  size="icon"
                  variant="ghost"
                  className="h-6 w-6 text-muted-foreground hover:text-foreground"
                  onClick={() => {
                    setTargetBucket(col.id);
                    setAddDialogOpen(true);
                  }}
                  title={`Add task to ${col.title}`}
                >
                  <Plus className="h-3.5 w-3.5" />
                </Button>
              </div>

              {/* Cards List */}
              <div className="flex-1 space-y-2.5">
                {colItems.length === 0 && (
                  <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border/80 p-6 text-center text-xs text-muted-foreground">
                    <p className="italic">No tasks in this bucket.</p>
                    <p className="text-[10px]">Drag tasks here or click +</p>
                  </div>
                )}

                {colItems.map((item) => (
                  <div
                    key={item.id}
                    draggable
                    onDragStart={(e) => handleDragStart(e, item.id)}
                    onClick={() => {
                      setSelectedItem(item);
                      setDetailOpen(true);
                    }}
                    className="group relative flex flex-col gap-2 rounded-lg border border-border/90 bg-card p-3 shadow-xs hover:border-primary/50 hover:shadow-sm cursor-grab active:cursor-grabbing transition-all"
                  >
                    {/* Card Top: Priority & Status */}
                    <div className="flex items-center justify-between gap-1.5">
                      <div className="flex items-center gap-1.5">
                        <GripVertical className="h-3 w-3 text-muted-foreground opacity-40 group-hover:opacity-100" />
                        <Badge
                          variant="outline"
                          className={`text-[9px] px-1.5 py-0 font-medium uppercase ${
                            item.priority === "high"
                              ? "border-red-500/30 text-red-500 bg-red-500/10"
                              : item.priority === "med" || item.priority === "medium"
                                ? "border-amber-500/30 text-amber-500 bg-amber-500/10"
                                : "border-blue-500/30 text-blue-500 bg-blue-500/10"
                          }`}
                        >
                          <Flame className="h-2.5 w-2.5 mr-0.5" />
                          {item.priority}
                        </Badge>
                      </div>

                      {/* Status Button Toggle */}
                      <button
                        type="button"
                        onClick={(e) => handleStatusCycle(e, item)}
                        className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
                          item.status === "done"
                            ? "bg-verified/15 text-verified"
                            : item.status === "doing"
                              ? "bg-amber-500/15 text-amber-500"
                              : "bg-muted text-muted-foreground"
                        }`}
                        title="Click to advance status"
                      >
                        {item.status === "done" ? (
                          <CheckCircle2 className="h-3 w-3" />
                        ) : item.status === "doing" ? (
                          <Clock className="h-3 w-3" />
                        ) : (
                          <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground" />
                        )}
                        <span className="capitalize">{item.status}</span>
                      </button>
                    </div>

                    {/* Title */}
                    <p className="text-xs font-semibold text-foreground line-clamp-2">
                      {item.title}
                    </p>

                    {/* Description preview */}
                    {item.description && (
                      <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
                        {item.description}
                      </p>
                    )}

                    {/* Linked Claims & Footer */}
                    {item.linked_claims && item.linked_claims.length > 0 && (
                      <div className="flex items-center gap-1 text-[10px] text-muted-foreground pt-1 border-t border-border/50">
                        <Tag className="h-3 w-3 text-primary" />
                        <span>{item.linked_claims.length} grounded claims</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Card Detail Sheet */}
      <PlanCardDetailDrawer
        item={selectedItem}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        handoverId={handoverId}
      />

      {/* Add Custom Task Dialog */}
      <AddPlanItemDialog
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        handoverId={handoverId}
        defaultDayBucket={targetBucket}
      />
    </div>
  );
}
