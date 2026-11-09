import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth, type Role } from "@/lib/api/auth";

export interface ProtectedRouteProps {
  allowedRoles?: Role[];
}

export function ProtectedRoute({ allowedRoles }: ProtectedRouteProps) {
  const { user, isLoading, isAuthenticated } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <span className="grid size-9 place-items-center rounded-md bg-primary font-mono text-sm font-semibold text-primary-foreground animate-pulse">
            R
          </span>
          <p className="font-mono text-xs text-muted-foreground">Authenticating RelayOps...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center p-8 text-center">
        <h2 className="text-lg font-bold text-destructive">Unauthorized Access</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Your role ({user.role}) does not have permission to access this section.
        </p>
      </div>
    );
  }

  return <Outlet />;
}
