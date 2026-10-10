import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { StressAlertBanner } from "@/components/live/StressAlertBanner";
import { useLiveStore } from "@/stores/liveStore";
import type { Prediction } from "@/api/types";

function highStress(ts: number): Prediction {
  return {
    timestamp_ms: ts,
    label: "stress",
    confidence: 0.92,
    smoothed_label: "stress",
    smoothed_confidence: 0.9, // smoothed P(stress) = 0.9 ≥ 0.7
    raw_proba: { baseline: 0.08, stress: 0.92 },
    calibration_applied: false,
  };
}

describe("breathing auto-trigger (StressAlertBanner)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(0);
    useLiveStore.getState().reset();
  });
  afterEach(() => vi.useRealTimers());

  it("appears only after sustained (>30s) high smoothed stress", () => {
    render(
      <MemoryRouter>
        <StressAlertBanner />
      </MemoryRouter>,
    );

    // First elevated emit - not yet sustained.
    act(() => useLiveStore.getState().pushPrediction(highStress(1000)));
    expect(screen.queryByText(/Stress has been elevated/)).toBeNull();

    // Advance >30s of wall-clock and emit again → sustained.
    act(() => {
      vi.setSystemTime(31_000);
      useLiveStore.getState().pushPrediction(highStress(31_000));
    });
    expect(screen.getByText(/Stress has been elevated/)).toBeInTheDocument();
    expect(screen.getByText("Try breathing")).toBeInTheDocument();
  });

  it("does not appear when stress subsides before 30s", () => {
    render(
      <MemoryRouter>
        <StressAlertBanner />
      </MemoryRouter>,
    );
    act(() => useLiveStore.getState().pushPrediction(highStress(1000)));
    act(() => {
      vi.setSystemTime(10_000);
      // Stress drops (baseline) → streak resets.
      useLiveStore.getState().pushPrediction({
        ...highStress(10_000),
        smoothed_label: "baseline",
        smoothed_confidence: 0.8, // smoothed P(stress) = 0.2
      });
    });
    expect(screen.queryByText(/Stress has been elevated/)).toBeNull();
  });
});
