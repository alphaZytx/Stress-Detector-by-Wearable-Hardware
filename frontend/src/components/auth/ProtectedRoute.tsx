import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";

/**
 * Gate for authenticated routes. Reads auth from the store and decodes the JWT
 * client-side to check expiry (no round-trip needed just for routing). On
 * failure, redirects to /login carrying a return-to location.
 */
export function ProtectedRoute() {
  const location = useLocation();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <Outlet />;
}
