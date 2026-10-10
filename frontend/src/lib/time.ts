/** Time helpers. All backend timestamps are epoch ms (or stream-relative ms). */

export function formatClock(ms: number): string {
  return new Date(ms).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateTime(ms: number): string {
  return new Date(ms).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Duration between two epoch-ms instants as "Xm Ys" (or "-" if open/unknown). */
export function formatDuration(startMs: number, endMs: number | null): string {
  if (endMs == null) return "-";
  return formatElapsed(Math.max(0, endMs - startMs));
}

/** Elapsed ms → "Xm Ys" / "Ys". */
export function formatElapsed(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return m > 0 ? `${m}m ${s.toString().padStart(2, "0")}s` : `${s}s`;
}

/** "mm:ss" for countdowns. */
export function formatMmSs(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
