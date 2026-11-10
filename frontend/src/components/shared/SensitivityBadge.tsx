import * as React from "react";
import { Lock, Unlock, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export interface SensitivityBadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  level: number; // 0, 1, 2, 3
  size?: "sm" | "default";
}

const SENSITIVITY_CONFIG: Record<
  number,
  {
    name: string;
    description: string;
    className: string;
    icon: React.ComponentType<{ className?: string }>;
  }
> = {
  0: {
    name: "Public",
    description: "Clearance Level 0: Unrestricted project activity, safe for external viewers.",
    className: "border-card-border bg-canvas-2 text-ink-muted",
    icon: Unlock,
  },
  1: {
    name: "Internal",
    description: "Clearance Level 1: Internal team visibility. Standard code and architecture.",
    className: "border-brand/25 bg-brand-soft text-brand-text",
    icon: Lock,
  },
  2: {
    name: "Confidential",
    description:
      "Clearance Level 2: Private team discussions, incident reviews, and financial references.",
    className: "border-needs-review/25 bg-warn-soft text-needs-review",
    icon: Lock,
  },
  3: {
    name: "Restricted",
    description:
      "Clearance Level 3: Highly sensitive credentials, salary/HR deliberations, lead-only artifacts.",
    className: "border-conflict/30 bg-danger-soft text-conflict font-semibold",
    icon: ShieldAlert,
  },
};

export function SensitivityBadge({
  level,
  size = "default",
  className,
  ...props
}: SensitivityBadgeProps) {
  const config = SENSITIVITY_CONFIG[level] ?? SENSITIVITY_CONFIG[0];
  const Icon = config.icon;

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant="outline"
            className={cn(
              "inline-flex cursor-default items-center gap-1 font-mono transition-colors",
              size === "sm" ? "px-1.5 py-0.2 text-[10px]" : "px-2 py-0.5 text-xs",
              config.className,
              className,
            )}
            {...props}
          >
            <Icon className={size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3"} />
            <span>L{level}</span>
            <span className="font-sans font-normal opacity-90">{config.name}</span>
          </Badge>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs text-xs">
          <p className="font-semibold">
            {config.name} (Clearance Level {level})
          </p>
          <p className="mt-1 text-ink-muted">{config.description}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
