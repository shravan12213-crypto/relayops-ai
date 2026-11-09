import * as React from "react";
import { RefreshCw, WifiOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/system";

export function OfflineBanner() {
  const [isOnline, setIsOnline] = React.useState<boolean>(() =>
    typeof navigator !== "undefined" ? navigator.onLine : true
  );
  const { isError, refetch, isFetching } = useHealth();

  React.useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const isDisconnected = !isOnline || isError;

  if (!isDisconnected) return null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="sticky top-0 z-50 flex items-center justify-between border-b border-destructive/40 bg-destructive/10 px-4 py-2 text-xs text-foreground backdrop-blur-sm transition-all"
    >
      <div className="flex items-center gap-2">
        <WifiOff className="h-4 w-4 text-destructive shrink-0" />
        <span>
          <strong>Connection Interrupted:</strong> Unable to communicate with the RelayOps backend API. Reconnecting in background...
        </span>
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={() => refetch()}
        disabled={isFetching}
        className="h-6 gap-1 px-2 text-[11px] border-destructive/40 hover:bg-destructive/15 text-foreground"
      >
        <RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} />
        <span>Retry Connection</span>
      </Button>
    </div>
  );
}
