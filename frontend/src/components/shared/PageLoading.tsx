import { Loader2 } from "lucide-react";

export function PageLoading() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-[50vh] flex-col items-center justify-center gap-3 text-muted-foreground animate-in fade-in-50 duration-200"
    >
      <Loader2 className="h-6 w-6 animate-spin text-primary" />
      <span className="text-xs font-medium">Loading view...</span>
      <span className="sr-only">Loading page content</span>
    </div>
  );
}
