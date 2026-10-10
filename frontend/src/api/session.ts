import { API_BASE, api } from "./client";
import type { SessionExport, SessionInfo, SessionSummary } from "./types";
import { useAuthStore } from "@/stores/authStore";

export const sessionApi = {
  start: (userLabel?: string, notes?: string, useCalibration = true) =>
    api.post<{ session_id: string }>("/session/start", {
      user_label: userLabel || null,
      notes: notes || null,
      use_calibration: useCalibration,
    }),

  stop: () => api.post<{ session_id: string | null }>("/session/stop"),

  label: (timestampMs: number, label: string, sessionId?: string) =>
    api.post<{ status: string }>("/session/label", {
      timestamp_ms: timestampMs,
      label,
      session_id: sessionId ?? null,
    }),

  list: () => api.get<SessionInfo[]>("/session/list"),

  /** History-list rows with the dominant state precomputed server-side (one
   * round trip instead of an export fetch per session). */
  summaries: () => api.get<SessionSummary[]>("/session/summaries"),

  exportData: (sessionId: string, format: "json" | "csv" = "json") =>
    api.get<SessionExport>(`/session/${sessionId}/export?format=${format}`),

  remove: (sessionId: string) =>
    api.del<{ status: string }>(`/session/${sessionId}`),
};

/**
 * Trigger a browser download of a session export. The Authorization header can't
 * ride on a plain <a href>, so we fetch the file as a blob and save it.
 */
export async function downloadSessionExport(
  sessionId: string,
  format: "json" | "csv",
): Promise<void> {
  const token = useAuthStore.getState().token;
  const resp = await fetch(
    `${API_BASE}/session/${sessionId}/export?format=${format}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} },
  );
  if (!resp.ok) throw new Error(`Export failed (${resp.status})`);
  const blob = await resp.blob();
  saveBlob(blob, `session-${sessionId}.${format}`);
}

/** Download a ZIP of all of the current user's sessions. */
export async function downloadAllSessions(): Promise<void> {
  const token = useAuthStore.getState().token;
  const resp = await fetch(`${API_BASE}/session/export-all`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) throw new Error(`Export failed (${resp.status})`);
  saveBlob(await resp.blob(), "sessions.zip");
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
