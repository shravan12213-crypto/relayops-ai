import { Sparkles } from "lucide-react";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export interface ConfidenceMeterProps {
  confidence: number; // 0.0 to 1.0
  className?: string;
}

export function ConfidenceMeter({ confidence, className }: ConfidenceMeterProps) {
  const pct = Math.round(confidence * 100);

  const getTier = (score: number) => {
    if (score >= 85) {
      return {
        label: "High Confidence",
        barColor: "bg-verified",
        textColor: "text-verified",
        description: "Backed by high-authority source code, PRs, or exact doc references.",
      };
    }
    if (score >= 65) {
      return {
        label: "Medium Confidence",
        barColor: "bg-needs-review",
        textColor: "text-needs-review",
        description: "Derived from ticket descriptions or discussion threads; review recommended.",
      };
    }
    return {
      label: "Low Confidence",
      barColor: "bg-conflict",
      textColor: "text-conflict",
      description: "Weak evidence or chat mentions; requires human verification before sign-off.",
    };
  };

  const tier = getTier(pct);

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              "inline-flex cursor-default items-center gap-1.5 rounded border border-border/80 bg-muted/40 px-2 py-0.5 font-mono text-[11px]",
              className,
            )}
          >
            <Sparkles className={cn("h-3 w-3", tier.textColor)} />
            <span className="font-semibold">{pct}%</span>
            <div className="h-1.5 w-10 overflow-hidden rounded-full bg-secondary">
              <div
                className={cn("h-full transition-all duration-300", tier.barColor)}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs text-xs">
          <p className="font-semibold text-foreground">
            {tier.label} ({pct}%)
          </p>
          <p className="mt-1 text-muted-foreground">{tier.description}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
