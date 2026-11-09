import * as React from "react";
import { ArrowLeft, FileQuestion } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  React.useEffect(() => {
    document.title = "404 Not Found — RelayOps";
  }, []);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted text-muted-foreground shadow-sm">
        <FileQuestion className="h-8 w-8" />
      </div>
      <h1 className="mt-4 text-3xl font-extrabold tracking-tight text-foreground">404</h1>
      <h2 className="mt-1 text-sm font-semibold text-foreground">Page Not Found</h2>
      <p className="mt-2 max-w-sm text-xs text-muted-foreground">
        The requested URL was not found in RelayOps. Please check the route or return to the
        dashboard.
      </p>
      <Button asChild size="sm" className="mt-6 gap-2 text-xs">
        <Link to="/">
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Dashboard
        </Link>
      </Button>
    </div>
  );
}
