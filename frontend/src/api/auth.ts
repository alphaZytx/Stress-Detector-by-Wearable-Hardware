import { api } from "./client";
import type { TokenResponse, UserInfo } from "./types";

export const authApi = {
  register: (email: string, password: string, displayName?: string) =>
    api.post<TokenResponse>(
      "/auth/register",
      { email, password, display_name: displayName || null },
      true,
    ),

  login: (email: string, password: string) =>
    api.post<TokenResponse>("/auth/login", { email, password }, true),

  me: () => api.get<UserInfo>("/auth/me"),

  logout: () => api.post<{ status: string }>("/auth/logout"),
};
