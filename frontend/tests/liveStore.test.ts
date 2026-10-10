import { beforeEach, describe, expect, it } from "vitest";
import { useLiveStore } from "@/stores/liveStore";
import type { Prediction, SensorSample } from "@/api/types";

function sample(ts: number): SensorSample {
  return {
    timestamp_ms: ts,
    bpm: 72,
    avg_bpm: 72,
    temp_c: 36.5,
    gsr: 100,
    source_label: null,
  };
}

function prediction(ts: number): Prediction {
  return {
    timestamp_ms: ts,
    label: "stress",
    confidence: 0.8,
    smoothed_label: "stress",
    smoothed_confidence: 0.75,
    raw_proba: { baseline: 0.2, stress: 0.8 },
    calibration_applied: false,
  };
}

describe("liveStore", () => {
  beforeEach(() => useLiveStore.getState().reset());

  it("tracks the latest sample and prediction", () => {
    const s = useLiveStore.getState();
    s.pushSample(sample(1000));
    s.pushPrediction(prediction(1000));
    expect(useLiveStore.getState().latestSample?.timestamp_ms).toBe(1000);
    expect(useLiveStore.getState().latestPrediction?.smoothed_label).toBe("stress");
  });

  it("caps the prediction buffer at 24 emits", () => {
    const s = useLiveStore.getState();
    for (let i = 0; i < 50; i++) s.pushPrediction(prediction(i));
    expect(useLiveStore.getState().predictions.length).toBe(24);
    // Oldest dropped, newest kept.
    expect(useLiveStore.getState().predictions[23].timestamp_ms).toBe(49);
  });

  it("reset clears buffers", () => {
    const s = useLiveStore.getState();
    s.pushSample(sample(1));
    s.reset();
    expect(useLiveStore.getState().samples.length).toBe(0);
    expect(useLiveStore.getState().latestSample).toBeNull();
  });

  it("status transitions are recorded", () => {
    useLiveStore.getState().setStatus("reconnecting");
    expect(useLiveStore.getState().status).toBe("reconnecting");
  });
});
