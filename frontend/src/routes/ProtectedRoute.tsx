import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import type { Role } from "@/types/enums";

/**
 * Section 27/49.14: the frontend guard is a UX convenience only — every
 * backend endpoint independently re-checks role/scope server-side. This
 * never substitutes for that; it just avoids showing a screen the API
 * would reject anyway.
 */
export function ProtectedRoute({ allow }: { allow?: Role[] }) {
  const { isAuthenticated, activeRole, isBootstrapping } = useAuth();

  // Fix #3: don't decide "authenticated" purely from localStorage — wait
  // for the startup /auth/me validation to resolve first, so an
  // expired/revoked token can't render protected UI even momentarily.
  if (isBootstrapping) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-paper">
        <div className="w-6 h-6 border-2 border-navy border-t-transparent rounded-full animate-spin" aria-label="Loading" />
      </div>
    );
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (allow && activeRole && !allow.includes(activeRole)) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}
