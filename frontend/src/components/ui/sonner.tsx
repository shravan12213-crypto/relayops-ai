import type { ComponentProps } from "react";
import { Toaster as Sonner } from "sonner";

import { useTheme } from "@/app/theme-context";

type ToasterProps = ComponentProps<typeof Sonner>;

const Toaster = (props: ToasterProps) => {
  const { theme } = useTheme();

  return (
    <Sonner
      theme={theme}
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:rounded-2xl group-[.toaster]:border-card-border group-[.toaster]:bg-card group-[.toaster]:text-ink group-[.toaster]:shadow-card",
          description: "group-[.toast]:text-ink-muted",
          actionButton: "group-[.toast]:bg-dark group-[.toast]:text-dark-fg",
          cancelButton: "group-[.toast]:bg-canvas-2 group-[.toast]:text-ink-muted",
        },
      }}
      {...props}
    />
  );
};

export { Toaster };
