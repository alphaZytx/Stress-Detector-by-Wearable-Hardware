/** Display formatting for biosignal values. */

/** Round to n decimals, render "-" for null/NaN. */
export function fmt(value: number | null | undefined, decimals = 0): string {
  if (value == null || Number.isNaN(value)) return "-";
  return value.toFixed(decimals);
}

export function fmtBpm(value: number | null | undefined): string {
  return fmt(value, 0);
}

export function fmtTemp(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value) || value === 0) return "-";
  return value.toFixed(1);
}

export function fmtPercent(fraction: number, decimals = 0): string {
  return `${(fraction * 100).toFixed(decimals)}%`;
}

/** Trend over a numeric series: "up" | "down" | "flat". */
export function trend(values: number[], epsilon = 0.5): "up" | "down" | "flat" {
  const clean = values.filter((v) => v != null && !Number.isNaN(v));
  if (clean.length < 2) return "flat";
  const delta = clean[clean.length - 1] - clean[0];
  if (delta > epsilon) return "up";
  if (delta < -epsilon) return "down";
  return "flat";
}
