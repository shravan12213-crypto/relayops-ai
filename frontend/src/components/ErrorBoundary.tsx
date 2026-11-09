import * as React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("Uncaught RelayOps application error:", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <h1 className="mt-4 text-xl font-bold tracking-tight text-foreground">
            Application Error
          </h1>
          <p className="mt-2 max-w-md text-xs text-muted-foreground">
            An unexpected error occurred while rendering this interface.
          </p>
          {this.state.error?.message && (
            <pre className="mt-4 max-w-lg overflow-x-auto rounded border bg-muted p-3 text-left font-mono text-[11px] text-destructive">
              {this.state.error.message}
            </pre>
          )}
          <Button type="button" onClick={this.handleReset} className="mt-6 gap-2 text-xs">
            <RefreshCw className="h-3.5 w-3.5" />
            Reload RelayOps
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
