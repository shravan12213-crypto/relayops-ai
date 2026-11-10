import * as React from "react";
import {
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  HelpCircle,
  FileEdit,
  Check,
  Ban,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type StatusType =
  | "verified"
  | "needs_review"
  | "needs-review"
  | "conflict"
  | "unverified"
  | "draft"
  | "accepted"
  | "rejected"
  | "edited"
  | "signed"
  | "delivered";

export interface StatusBadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  status: StatusType | string;
  showIcon?: boolean;
  size?: "sm" | "default";
}

const STATUS_CONFIG: Record<
  string,
  {
    label: string;
    className: string;
    dotColor: string;
    icon: React.ComponentType<{ className?: string }>;
  }
> = {
  verified: {
    label: "Verified",
    className: "border-verified/20 bg-brand-soft text-verified",
    dotColor: "bg-verified",
    icon: CheckCircle2,
  },
  needs_review: {
    label: "Needs Review",
    className: "border-needs-review/20 bg-warn-soft text-needs-review",
    dotColor: "bg-needs-review",
    icon: AlertTriangle,
  },
  "needs-review": {
    label: "Needs Review",
    className: "border-needs-review/20 bg-warn-soft text-needs-review",
    dotColor: "bg-needs-review",
    icon: AlertTriangle,
  },
  conflict: {
    label: "Conflict",
    className: "border-conflict/20 bg-danger-soft text-conflict",
    dotColor: "bg-conflict",
    icon: AlertCircle,
  },
  unverified: {
    label: "Unverified",
    className: "border-unverified/20 bg-canvas-2 text-unverified",
    dotColor: "bg-unverified",
    icon: HelpCircle,
  },
  accepted: {
    label: "Accepted",
    className: "border-verified/20 bg-brand-soft text-verified",
    dotColor: "bg-verified",
    icon: Check,
  },
  draft: {
    label: "Draft",
    className: "border-card-border bg-canvas-2 text-ink-muted",
    dotColor: "bg-ink-muted",
    icon: HelpCircle,
  },
  rejected: {
    label: "Rejected",
    className: "border-conflict/20 bg-danger-soft text-destructive",
    dotColor: "bg-destructive",
    icon: Ban,
  },
  edited: {
    label: "Human Edited",
    className: "border-brand/25 bg-brand-soft text-brand-text",
    dotColor: "bg-brand",
    icon: FileEdit,
  },
  signed: {
    label: "Signed",
    className: "border-verified/20 bg-brand-soft text-verified",
    dotColor: "bg-verified",
    icon: CheckCircle2,
  },
  delivered: {
    label: "Delivered",
    className: "border-brand/25 bg-brand-soft text-brand-text",
    dotColor: "bg-brand",
    icon: CheckCircle2,
  },
};

export function StatusBadge({
  status,
  showIcon = true,
  size = "default",
  className,
  ...props
}: StatusBadgeProps) {
  const normalizedKey = status.toLowerCase().replace(/[\s-]/g, "_");
  const config = STATUS_CONFIG[normalizedKey] || {
    label: status,
    className: "border-card-border bg-canvas-2 text-ink-muted",
    dotColor: "bg-ink-muted",
    icon: HelpCircle,
  };

  const Icon = config.icon;

  return (
    <Badge
      variant="outline"
      className={cn(
        "inline-flex items-center gap-1.5 font-medium transition-colors",
        size === "sm" ? "px-1.5 py-0.5 text-[11px]" : "px-2.5 py-0.5 text-xs",
        config.className,
        className,
      )}
      {...props}
    >
      {showIcon ? (
        <Icon className={cn("shrink-0", size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5")} />
      ) : (
        <span className={cn("size-1.5 rounded-full shrink-0", config.dotColor)} />
      )}
      <span>{config.label}</span>
    </Badge>
  );
}
