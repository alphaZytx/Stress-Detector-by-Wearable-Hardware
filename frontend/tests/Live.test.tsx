import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Live } from "@/routes/Live";
import { useLiveStore } from "@/stores/liveStore";
import type { FeatureVector, Prediction, SensorSample } from "@/api/types";

// Recharts' ResponsiveContainer needs a non-zero size in jsdom.
beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockReturnValue(600);
  vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(300);
});

function seedStore() {
  const s = useLiveStore.getState();
  s.reset();
  s.setStatus("open");
  const sample: SensorSample = {
    timestamp_ms: 60000,
    bpm: 88,
    avg_bpm: 86,
    temp_c: 34.2,
    gsr: 142,
    source_label: null,
  };
  for (let i = 0; i < 40; i++) {
    s.pushSample({ ...sample, timestamp_ms: i * 1000, bpm: 80 + (i % 10) });
  }
  s.pushSample(sample);

  const features = { hr_pnn_proxy: 0.123 } as FeatureVector;
  s.pushFeatures(features);

  const pred: Prediction = {
    timestamp_ms: 60000,
    label: "stress",
    confidence: 0.9,
    smoothed_label: "stress",
    smoothed_confidence: 0.85,
    raw_proba: { baseline: 0.1, stress: 0.9 },
    calibration_applied: true,
  };
  s.pushPrediction(pred);
}

describe("Live view", () => {
  it("renders all gauges and the stress indicator from the live store", () => {
    act(() => seedStore());
    render(
      <MemoryRouter>
        <Live />
      </MemoryRouter>,
    );

    // Stress indicator shows the smoothed label + calibrated flag.
    expect(screen.getByText("STRESS")).toBeInTheDocument();
    expect(screen.getByText("calibrated")).toBeInTheDocument();

    // Gauge labels + values. "Heart rate" appears on both the chart and the
    // gauge - both are expected.
    expect(screen.getAllByText("Heart rate").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("88")).toBeInTheDocument(); // latest bpm
    expect(screen.getByText("GSR")).toBeInTheDocument();
    expect(screen.getByText("142")).toBeInTheDocument(); // latest gsr
    // Like "Heart rate", "Temperature" now appears on the gauge AND in the
    // ModelInputPanel (filter chip + group header) - all are expected.
    expect(screen.getAllByText("Temperature").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("34.2")).toBeInTheDocument();

    // HRV proxy value - shown on the HrvPanel and again as the panel's
    // hr_pnn_proxy row, so match on at least one.
    expect(screen.getAllByText("0.123").length).toBeGreaterThanOrEqual(1);

    // Connection pill + session controls present.
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("Start recording")).toBeInTheDocument();
  });
});
