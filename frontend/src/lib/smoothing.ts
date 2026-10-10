/** Small display-only smoothing helpers for noisy live sensor readings. */

/**
 * Rolling mean that preserves missing values until a valid reading appears.
 * This affects presentation only; model inference continues to use raw data.
 */
export function rollingMean(
  values: (number | null | undefined)[],
  windowSize = 5,
): (number | null)[] {
  return values.map((_, index) => {
    const start = Math.max(0, index - windowSize + 1);
    const window = values
      .slice(start, index + 1)
      .filter((value): value is number => value != null && Number.isFinite(value));
    if (window.length === 0) return null;
    return window.reduce((sum, value) => sum + value, 0) / window.length;
  });
}

/** The latest value from a rolling mean. */
export function smoothedLatest(
  values: (number | null | undefined)[],
  windowSize = 5,
): number | null {
  const smoothed = rollingMean(values, windowSize);
  return smoothed.length > 0 ? smoothed[smoothed.length - 1] : null;
}
