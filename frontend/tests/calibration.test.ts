import { describe, expect, it } from "vitest";
import { computeCalibration } from "@/lib/calibration";
import type { SensorSample } from "@/api/types";

function sample(overrides: Partial<SensorSample>): SensorSample {
  return {
    timestamp_ms: 0,
    bpm: 72,
    avg_bpm: 72,
    temp_c: 33.5,
    gsr: 66,
    source_label: null,
    ...overrides,
  };
}

/** A clean 120-sample resting window with mild HR variation. */
function restingWindow(): SensorSample[] {
  return Array.from({ length: 120 }, (_, i) =>
    sample({ timestamp_ms: i * 1000, bpm: 70 + (i % 5), gsr: 64 + (i % 4) }),
  );
}

describe("computeCalibration", () => {
  it("accepts a clean resting window and computes baselines", () => {
    const r = computeCalibration(restingWindow());
    expect(r.ok).toBe(true);
    expect(r.warnings).toHaveLength(0);
    expect(r.hr?.n).toBe(120);
    expect(r.hr?.mean).toBeGreaterThan(69);
    expect(r.hr?.mean).toBeLessThan(75);
    expect(r.gsr.mean).toBeGreaterThan(63);
  });

  it("rejects when too few valid HR samples", () => {
    const window = restingWindow().map((s, i) =>
      i < 100 ? { ...s, bpm: null } : s,
    );
    const r = computeCalibration(window);
    expect(r.ok).toBe(false);
    expect(r.warnings.some((w) => w.includes("valid heart-rate"))).toBe(true);
  });

  it("rejects when HR variance is unphysiologically low (sensor off)", () => {
    const window = restingWindow().map((s) => ({ ...s, bpm: 72 }));
    const r = computeCalibration(window);
    expect(r.ok).toBe(false);
    expect(r.warnings.some((w) => w.includes("disconnected"))).toBe(true);
  });
});
