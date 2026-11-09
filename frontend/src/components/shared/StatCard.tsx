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
    default: "",
    verified: "border-l-4 border-l-verified",
    "needs-review": "border-l-4 border-l-needs-review",
    conflict: "border-l-4 border-l-conflict",
    primary: "border-l-4 border-l-primary",
  }[accent];

  return (
    <Card
      className={cn(
        "relative overflow-hidden transition-all duration-200 hover:shadow-sm",
        accentClasses,
        className,
      )}
      {...props}
    >
      <CardContent className="p-5">
        <div className="flex items-center justify-between space-x-2">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {title}
          </p>
          {Icon && (
            <div className="rounded-md bg-muted/60 p-1.5 text-muted-foreground">
              <Icon className="h-4 w-4" />
            </div>
          )}
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-mono text-2xl font-bold tracking-tight text-foreground">
            {value}
          </span>
        </div>
        {description && <p className="mt-1 text-xs text-muted-foreground">{description}</p>}
      </CardContent>
    </Card>
  );
}
