import * as React from "react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface StatCardProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string;
  value: string | number;
  description?: string;
  icon?: React.ComponentType<{ className?: string }>;
  accent?: "default" | "verified" | "needs-review" | "conflict" | "primary";
}

export function StatCard({
  title,
  value,
  description,
  icon: Icon,
  accent = "default",
  className,
  ...props
}: StatCardProps) {
  const accentClasses = {
    default: "bg-canvas-2 text-ink-muted",
    verified: "bg-brand-soft text-verified",
    "needs-review": "bg-warn-soft text-needs-review",
    conflict: "bg-danger-soft text-conflict",
    primary: "bg-brand-soft text-brand-text",
  }[accent];

  return (
    <Card
      className={cn(
        "relative overflow-hidden transition-shadow duration-200 hover:shadow-card-hover",
        accentClasses,
        className,
      )}
      {...props}
    >
      <CardContent className="p-5">
        <div className="flex items-center justify-between space-x-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-muted">
            {title}
          </p>
          {Icon && (
            <div className={cn("grid size-10 shrink-0 place-items-center rounded-full", accentClasses)}>
              <Icon className="h-[18px] w-[18px]" />
            </div>
          )}
        </div>
        <div className="mt-4 flex items-baseline gap-2">
          <span className="text-[44px] font-semibold leading-none tracking-[-0.02em] text-ink tabular">
            {value}
          </span>
        </div>
        {description && <p className="mt-1.5 text-xs text-ink-muted">{description}</p>}
      </CardContent>
    </Card>
  );
}
