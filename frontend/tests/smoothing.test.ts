import { describe, expect, it } from "vitest";
import { rollingMean, smoothedLatest } from "@/lib/smoothing";

describe("live display smoothing", () => {
  it("averages readings over the requested rolling window", () => {
    expect(rollingMean([70, 80, 90, 100], 3)).toEqual([70, 75, 80, 90]);
  });

  it("ignores missing and non-finite sensor readings", () => {
    expect(smoothedLatest([70, null, Number.NaN, 80], 4)).toBe(75);
    expect(smoothedLatest([null, Number.NaN], 2)).toBeNull();
  });
});
