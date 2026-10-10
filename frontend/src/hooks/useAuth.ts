/** Auth actions + reactive auth state, wrapping the auth store + auth API. */

import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { authApi } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";

export function useAuth() {
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const setAuth = useAuthStore((s) => s.setAuth);
  const clear = useAuthStore((s) => s.clear);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const login = useCallback(
    async (email: string, password: string) => {
      const resp = await authApi.login(email, password);
      setAuth(resp);
      return resp;
    },
    [setAuth],
  );

  const register = useCallback(
    async (email: string, password: string, displayName?: string) => {
      const resp = await authApi.register(email, password, displayName);
      setAuth(resp);
      return resp;
    },
    [setAuth],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      /* stateless - ignore network errors on logout */
    }
    clear();
    navigate("/login");
  }, [clear, navigate]);

  return {
    token,
    user,
    isAuthenticated: isAuthenticated(),
    login,
    register,
    logout,
  };
}
