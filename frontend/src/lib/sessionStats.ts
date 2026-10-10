/** Client-side session summaries from exported samples/predictions. */

import type { SensorSample, SessionPredictionRow } from "@/api/types";

export interface DominantStress {
  level: "baseline" | "stress" | "none";
  stressFraction: number; // 0..1
  count: number;
}

/** Dominant stress level from the smoothed prediction labels. */
export function dominantStress(preds: SessionPredictionRow[]): DominantStress {
  if (preds.length === 0) return { level: "none", stressFraction: 0, count: 0 };
  const stress = preds.filter((p) => p.smoothed_label === "stress").length;
  const fraction = stress / preds.length;
  return {
    level: fraction >= 0.5 ? "stress" : "baseline",
    stressFraction: fraction,
    count: preds.length,
  };
}

function mean(values: number[]): number | null {
  const clean = values.filter((v) => v != null && !Number.isNaN(v));
  if (clean.length === 0) return null;
  return clean.reduce((a, b) => a + b, 0) / clean.length;
}

export interface SessionAverages {
  hr: number | null;
  gsr: number | null;
  temp: number | null;
}

export function sessionAverages(samples: SensorSample[]): SessionAverages {
  return {
    hr: mean(samples.map((s) => s.bpm).filter((b): b is number => b != null)),
    gsr: mean(samples.map((s) => s.gsr)),
    temp: mean(
      samples.map((s) => s.temp_c).filter((t): t is number => t != null && t > 0),
    ),
  };
}
