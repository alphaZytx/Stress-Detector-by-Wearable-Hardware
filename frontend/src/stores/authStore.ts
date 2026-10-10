/**
 * Auth store - JWT + user in localStorage (single-deployment auth, suitable for
 * a clinical pilot; production would need SSO + token revocation).
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { TokenResponse, UserInfo } from "@/api/types";
import { isTokenExpired } from "@/lib/jwt";

interface AuthState {
  token: string | null;
  user: UserInfo | null;
  setAuth: (resp: TokenResponse) => void;
  setUser: (user: UserInfo) => void;
  clear: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      setAuth: (resp) => set({ token: resp.access_token, user: resp.user }),
      setUser: (user) => set({ user }),
      clear: () => set({ token: null, user: null }),
      isAuthenticated: () => {
        const { token } = get();
        return !isTokenExpired(token);
      },
    }),
    { name: "stress-auth" },
  ),
);
