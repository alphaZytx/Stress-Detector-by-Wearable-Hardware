import { describe, expect, it } from "vitest";
import { FEATURE_COUNT, FEATURE_GROUPS } from "@/explain/featureGroups";
import { clamp01, stressColor } from "@/explain/primitives";

/**
 * The Explain page groups the 18 features for display. Grouping is cosmetic,
 * but it must not silently drop or invent a feature - if someone adds a 19th
 * feature to the model contract and forgets this file, the page would quietly
 * show 18 of 19 and look fine.
 */
describe("feature groups", () => {
  it("covers exactly the 18 contract features", () => {
    expect(FEATURE_COUNT).toBe(18);
  });

  it("lists every feature exactly once", () => {
    const all = FEATURE_GROUPS.flatMap((g) => g.keys);
    expect(new Set(all).size).toBe(all.length);
  });

  it("uses the canonical schema.py names and ordering within groups", () => {
    // Spot-check the two groups whose ordering is easiest to get wrong.
    expect(FEATURE_GROUPS[0].keys).toEqual([
      "hr_mean",
      "hr_std",
      "hr_min",
      "hr_max",
      "hr_range",
      "hr_slope",
      "hr_pnn_proxy",
    ]);
    expect(FEATURE_GROUPS[1].keys).toEqual([
      "gsr_mean",
      "gsr_std",
      "gsr_min",
      "gsr_max",
      "gsr_range",
      "gsr_slope",
      "gsr_auc",
      "gsr_peaks",
    ]);
  });
});

describe("clamp01", () => {
  it("passes through valid probabilities untouched", () => {
    expect(clamp01(0)).toBe(0);
    expect(clamp01(0.42)).toBe(0.42);
    expect(clamp01(1)).toBe(1);
  });

  it("clamps out-of-range values so bar widths can't overflow", () => {
    expect(clamp01(-0.5)).toBe(0);
    expect(clamp01(1.7)).toBe(1);
  });
});

describe("stressColor", () => {
  it("maps calm / moderate / high onto the app's three state tokens", () => {
    expect(stressColor(0.1)).toContain("success");
    expect(stressColor(0.5)).toContain("warning");
    expect(stressColor(0.9)).toContain("danger");
  });

  it("switches at the documented thresholds", () => {
    // Just below / at each boundary - these drive the dial colour, so a
    // silent shift here would change what the user sees at 0.4 and 0.66.
    expect(stressColor(0.39)).toContain("success");
    expect(stressColor(0.4)).toContain("warning");
    expect(stressColor(0.65)).toContain("warning");
    expect(stressColor(0.66)).toContain("danger");
  });
});
