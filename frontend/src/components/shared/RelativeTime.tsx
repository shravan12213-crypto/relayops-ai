import * as React from "react";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export interface RelativeTimeProps extends React.HTMLAttributes<HTMLSpanElement> {
  date: string | number | Date | null | undefined;
}

function formatRelativeTime(dateInput: Date): string {
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - dateInput.getTime()) / 1000);

  if (diffInSeconds < 30) {
    return "just now";
  }
  if (diffInSeconds < 60) {
    return `${diffInSeconds}s ago`;
  }
  const diffInMinutes = Math.floor(diffInSeconds / 60);
  if (diffInMinutes < 60) {
    return `${diffInMinutes}m ago`;
  }
  const diffInHours = Math.floor(diffInMinutes / 60);
  if (diffInHours < 24) {
    return `${diffInHours}h ago`;
  }
  const diffInDays = Math.floor(diffInHours / 24);
  if (diffInDays < 30) {
    return `${diffInDays}d ago`;
  }
  const diffInMonths = Math.floor(diffInDays / 30);
  if (diffInMonths < 12) {
    return `${diffInMonths}mo ago`;
  }
  return dateInput.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function RelativeTime({ date, className, ...props }: RelativeTimeProps) {
  if (!date) {
    return <span className={cn("text-muted-foreground", className)}>-</span>;
  }

  const parsedDate = typeof date === "string" || typeof date === "number" ? new Date(date) : date;
  if (isNaN(parsedDate.getTime())) {
    return <span className={cn("text-muted-foreground", className)}>-</span>;
  }

  const relativeText = formatRelativeTime(parsedDate);
  const absoluteText = parsedDate.toISOString().replace("T", " ").substring(0, 19) + " UTC";

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <time
            dateTime={parsedDate.toISOString()}
            className={cn(
              "cursor-default text-xs text-muted-foreground transition-colors hover:text-foreground",
              className,
            )}
            {...props}
          >
            {relativeText}
          </time>
        </TooltipTrigger>
        <TooltipContent side="top" className="font-mono text-xs">
          {absoluteText}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
