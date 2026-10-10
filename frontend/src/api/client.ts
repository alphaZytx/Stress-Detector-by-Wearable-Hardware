/**
 * Fetch wrapper with JWT injection.
 *
 * The token is read lazily from the auth store on every request so it always
 * reflects the current session. A 401 clears auth (token expired/invalid) so the
 * ProtectedRoute bounces the user to /login.
 */

import { useAuthStore } from "@/stores/authStore";

export const API_BASE: string =
  import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8010";

export const WS_BASE: string =
  import.meta.env.VITE_WS_BASE ?? API_BASE.replace(/^http/, "ws");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Skip auth header (used by /auth/login, /auth/register, /demo/session). */
  anonymous?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";

  if (!opts.anonymous) {
    const token = useAuthStore.getState().token;
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const resp = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  if (resp.status === 401 && !opts.anonymous) {
    // Token invalid/expired - drop it so routing falls back to /login.
    useAuthStore.getState().clear();
  }

  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const data = await resp.json();
      detail = data.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(resp.status, detail);
  }

  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  get: <T>(path: string, anonymous = false) => request<T>(path, { anonymous }),
  post: <T>(path: string, body?: unknown, anonymous = false) =>
    request<T>(path, { method: "POST", body, anonymous }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

/** Build an authenticated download URL (token in query - for file downloads). */
export function downloadUrl(path: string): string {
  return `${API_BASE}${path}`;
}
