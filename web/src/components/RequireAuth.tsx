import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  const auth = useAuth();

  if (auth.isPending) {
    return <div className="p-6 text-sm text-fg-muted">...</div>;
  }
  if (auth.isError) {
    return <Navigate replace to="/login" state={{ from: location }} />;
  }
  return <>{children}</>;
}
