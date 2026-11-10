import * as React from "react";

import { cn } from "@/lib/utils";

export interface KbdProps extends React.HTMLAttributes<HTMLElement> {
  children: React.ReactNode;
}

export function Kbd({ className, children, ...props }: KbdProps) {
  return (
    <kbd
      className={cn(
        "inline-flex h-5 select-none items-center gap-1 rounded-md border border-card-border bg-canvas-2 px-1.5 font-mono text-[10px] font-medium text-ink-muted",
        className,
      )}
      {...props}
    >
      {children}
    </kbd>
  );
}
