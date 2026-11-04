/**
 * Compute a per-user resting baseline from a window of 1 Hz samples, with quality
 * gates. The personalized v3 model was trained with the same resting-reference
 * contract: HR/GSR become relative magnitudes and temperature becomes a delta.
 */

import type { SensorSample } from "@/api/types";

export interface BaselineStat {
  mean: number;
  std: number;
  n: number;
}

export interface CalibrationResult {
  ok: boolean;
  /** Reasons the capture was rejected (empty when ok). */
  warnings: string[];
  hr: BaselineStat | null;
  gsr: BaselineStat;
  temp: BaselineStat | null;
}

function stat(values: number[]): BaselineStat {
  const n = values.length;
  if (n === 0) return { mean: 0, std: 0, n: 0 };
  const mean = values.reduce((a, b) => a + b, 0) / n;
  const variance = values.reduce((a, b) => a + (b - mean) ** 2, 0) / n;
  return { mean, std: Math.sqrt(variance), n };
}

// Quality thresholds (documented heuristics).
const MIN_VALID_HR = 100; // of ~120 samples in a 2-min window
const MIN_VALID_TEMP = 100;
const MIN_HR_STD = 0.5; // lower → sensor likely disconnected (unphysiological)

export function computeCalibration(samples: SensorSample[]): CalibrationResult {
  const validHr = samples
    .map((s) => s.bpm)
    .filter((b): b is number => b != null);
  const validTemp = samples
    .map((s) => s.temp_c)
    .filter((t): t is number => t != null && t > 0);
  const gsr = stat(samples.map((s) => s.gsr));

  const hr = validHr.length > 0 ? stat(validHr) : null;
  const temp = validTemp.length > 0 ? stat(validTemp) : null;

  const warnings: string[] = [];
  if (validHr.length < MIN_VALID_HR)
    warnings.push(
      `Only ${validHr.length} valid heart-rate samples (need ≥${MIN_VALID_HR}). The sensor may have been noisy.`,
    );
  if (hr && hr.std < MIN_HR_STD)
    warnings.push(
      "Heart-rate variation was unusually low - the sensor may have been disconnected.",
    );
  if (validTemp.length < MIN_VALID_TEMP)
    warnings.push(
      `Only ${validTemp.length} valid object-temperature samples (need ≥${MIN_VALID_TEMP}). Keep your finger still on the sensor.`,
    );
  if (!Number.isFinite(gsr.mean) || Math.abs(gsr.mean) < 1e-9)
    warnings.push("GSR baseline was zero or invalid. Check the skin-contact sensor.");

  return { ok: warnings.length === 0, warnings, hr, gsr, temp };
}
