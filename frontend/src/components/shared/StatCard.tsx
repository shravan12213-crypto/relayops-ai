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
  const isHero = title.toLowerCase().includes("in review");
  const isZero = value === 0 || value === "0";
  const countNum = typeof value === "number" ? value : parseInt(String(value), 10) || 0;

  // Thin 3px accent bar at the top edge inside the card
  const accentBarColor = {
    default: "bg-ink-muted/30 dark:bg-ink-muted/20",
    verified: "bg-brand",
    "needs-review": "bg-warn",
    conflict: "bg-danger",
    primary: "bg-brand",
  }[accent];

  // 44px rounded-full icon container tint matching meaning
  const iconContainerClasses = {
    default: "bg-canvas-2 text-ink-muted",
    verified: "bg-brand-soft text-brand-text",
    "needs-review": "bg-warn-soft text-warn",
    conflict: "bg-danger-soft text-danger",
    primary: "bg-brand-soft text-brand-text",
  }[accent];

  return (
    <Card
      className={cn(
        "relative overflow-hidden rounded-[20px] transition-all [transition-duration:180ms] ease-out motion-safe:hover:-translate-y-0.5 hover:shadow-card-hover motion-reduce:transform-none motion-reduce:transition-none",
        isHero
          ? "border-transparent bg-[#0b2b26] text-white shadow-card dark:border-white/10 dark:bg-[#071a17]"
          : "border-card-border bg-card text-ink shadow-card",
        className,
      )}
      {...props}
    >
      {/* Decorative 3px accent bar */}
      <div
        className={cn(
          "pointer-events-none absolute inset-x-0 top-0 h-[3px] rounded-t-[20px]",
          accentBarColor,
        )}
      />

      <CardContent className="p-5 sm:p-6">
        <div className="flex flex-col gap-3">
          {/* Label Row with Top-Right Icon */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-h-[36px] flex-1 flex-col justify-center">
              <div className="flex flex-wrap items-center gap-1.5">
                <p
                  className={cn(
                    "text-[11px] font-semibold uppercase tracking-[0.06em] leading-snug",
                    isHero ? "text-white" : "text-ink-muted",
                  )}
                >
                  {title}
                </p>
                {isHero && countNum > 0 && (
                  <span className="inline-flex items-center rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-warn tracking-normal normal-case">
                    Needs action
                  </span>
                )}
              </div>
            </div>

            {Icon && (
              <div
                className={cn(
                  "grid size-11 shrink-0 place-items-center rounded-full",
                  isHero ? "bg-white/[0.12] text-warn" : iconContainerClasses,
                )}
              >
                <Icon className="h-5 w-5" />
              </div>
            )}
          </div>

          {/* Big Number Row */}
          <div className="flex items-baseline gap-2">
            <span
              className={cn(
                "font-sans text-[44px] font-semibold leading-none tracking-[-0.02em] tabular-nums",
                isHero
                  ? isZero
                    ? "text-white/40"
                    : "text-white"
                  : isZero
                    ? "text-ink-faint"
                    : "text-ink",
              )}
            >
              {value}
            </span>
          </div>

          {/* Caption */}
          {description && (
            <p
              className={cn(
                "text-[13px] leading-snug",
                isHero ? "text-white/70" : "text-ink-muted",
              )}
            >
              {description}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
