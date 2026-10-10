import { act } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModelInputPanel } from "@/components/live/ModelInputPanel";
import { FEATURE_KEYS, FEATURE_META } from "@/lib/featureMeta";
import { useLiveStore } from "@/stores/liveStore";
import type { FeatureVector, SensorSample } from "@/api/types";

/** The 18 columns, in the exact order the backend feeds the model. */
const CANONICAL = [
  "hr_mean", "hr_std", "hr_min", "hr_max", "hr_range", "hr_slope", "hr_pnn_proxy",
  "gsr_mean", "gsr_std", "gsr_min", "gsr_max", "gsr_range", "gsr_slope",
  "gsr_auc", "gsr_peaks",
  "temp_mean", "temp_std", "temp_slope",
];

function makeVector(seed: number): FeatureVector {
  return Object.fromEntries(
    FEATURE_META.map((m, i) => [m.key, seed + i]),
  ) as unknown as FeatureVector;
}

function seed() {
  const s = useLiveStore.getState();
  s.reset();
  s.setStatus("open");

  const sample: SensorSample = {
    timestamp_ms: 0, bpm: 72, avg_bpm: 72, temp_c: 34.2, gsr: 66,
    source_label: null,
  };
  for (let i = 0; i < 32; i++) {
    s.pushSample({ ...sample, timestamp_ms: i * 1000 });
  }
  // Two emits so rows have a previous value to diff against.
  s.pushFeatures(makeVector(10), 29000);
  s.pushFeatures(makeVector(12), 34000);
}

beforeEach(() => {
  act(() => seed());
});

describe("featureMeta", () => {
  it("matches the backend's canonical FEATURE_COLUMNS order", () => {
    expect(FEATURE_KEYS).toEqual(CANONICAL);
    expect(FEATURE_KEYS).toHaveLength(18);
  });
});

describe("ModelInputPanel", () => {
  it("renders the pipeline stages and the grouped feature vector", () => {
    render(<ModelInputPanel />);

    // Pipeline strip.
    expect(screen.getByText("Sensor stream")).toBeInTheDocument();
    expect(screen.getByText("Rolling window")).toBeInTheDocument();
    expect(screen.getByText("Feature vector")).toBeInTheDocument();
    expect(screen.getByText("SVM · RBF")).toBeInTheDocument();

    // "Heart rate" appears twice by design - as a filter chip and as the group
    // header - so assert on the group header specifically.
    expect(screen.getAllByText("Heart rate").length).toBeGreaterThanOrEqual(2);
    for (const key of CANONICAL) {
      expect(screen.getByText(key)).toBeInTheDocument();
    }
  });

  it("filters to a single sensor group", async () => {
    const user = userEvent.setup();
    render(<ModelInputPanel />);

    await user.click(screen.getByRole("button", { name: /Temperature/i }));

    expect(screen.getByText("temp_mean")).toBeInTheDocument();
    expect(screen.queryByText("hr_mean")).not.toBeInTheDocument();
  });

  it("expands a feature to reveal its description", async () => {
    const user = userEvent.setup();
    render(<ModelInputPanel />);

    const row = screen.getByText("gsr_peaks").closest("button")!;
    expect(row).toHaveAttribute("aria-expanded", "false");

    await user.click(row);

    expect(row).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByText(/Number of distinct skin-conductance responses/i),
    ).toBeInTheDocument();
  });

  it("freezes the readout so values stop updating while inspected", async () => {
    const user = userEvent.setup();
    render(<ModelInputPanel />);

    await user.click(screen.getByRole("button", { name: /Freeze/i }));

    // A new emit arrives while frozen - the panel keeps showing the snapshot.
    act(() => {
      useLiveStore.getState().pushFeatures(makeVector(900), 39000);
    });

    expect(screen.queryByText("900.0")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Resume/i }));
    expect(screen.getByText("900.0")).toBeInTheDocument();
  });
});

describe("ModelInputPanel · raw sensor mode", () => {
  it("switches to the raw packet stream and back", async () => {
    const user = userEvent.setup();
    render(<ModelInputPanel />);

    // Model mode by default.
    expect(screen.getByText("What the model sees")).toBeInTheDocument();
    expect(screen.getByText("hr_mean")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Raw sensors/i }));

    // Raw mode: the serial console, no derived feature keys, no pipeline stages.
    expect(screen.getByText("What the sensors send")).toBeInTheDocument();
    expect(screen.queryByText("hr_mean")).not.toBeInTheDocument();
    expect(screen.queryByText("Rolling window")).not.toBeInTheDocument();
    expect(
      screen.getByRole("log", { name: /raw sensor packet console/i }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Model input/i }));
    expect(screen.getByText("What the model sees")).toBeInTheDocument();
    expect(screen.getByText("hr_mean")).toBeInTheDocument();
  });

  it("marks PPG dropouts rather than interpolating them", async () => {
    const user = userEvent.setup();

    act(() => {
      // A packet with no heart rate - the real validity gate counts these.
      useLiveStore.getState().pushSample({
        timestamp_ms: 99000, bpm: null, avg_bpm: 71, temp_c: 34.2, gsr: 67,
        source_label: null,
      });
    });

    render(<ModelInputPanel />);
    await user.click(screen.getByRole("button", { name: /Raw sensors/i }));

    // The line prints the dropout flag and an em-dash placeholder, never a value.
    expect(screen.getByText(/\[DROP\]/)).toBeInTheDocument();
    // 1 dropout over the 33 buffered packets (32 seeded + this one).
    expect(
      screen.getByText((_, el) => el?.textContent === "dropouts 1/33"),
    ).toBeInTheDocument();
  });

  it("holds the raw stream steady while frozen", async () => {
    const user = userEvent.setup();
    render(<ModelInputPanel />);

    await user.click(screen.getByRole("button", { name: /Raw sensors/i }));
    await user.click(screen.getByRole("button", { name: /Freeze/i }));

    act(() => {
      useLiveStore.getState().pushSample({
        timestamp_ms: 123000, bpm: 188, avg_bpm: 188, temp_c: 39.9, gsr: 999,
        source_label: null,
      });
    });

    // The frozen snapshot must not show the packet that arrived after it.
    expect(screen.queryAllByText("999.0")).toHaveLength(0);

    // On resume the packet prints to the console.
    await user.click(screen.getByRole("button", { name: /Resume/i }));
    expect(screen.getAllByText("999.0").length).toBeGreaterThanOrEqual(1);
  });
});

describe("ensemble diagnostics", () => {
  const prediction = {
    timestamp_ms: 34000,
    label: "stress" as const,
    confidence: 0.82,
    smoothed_label: "stress" as const,
    smoothed_confidence: 0.77,
    raw_proba: { baseline: 0.18, stress: 0.82 },
    calibration_applied: false,
  };

  it("labels the model stage from the prediction's model_type", () => {
    act(() => {
      useLiveStore.getState().pushPrediction({ ...prediction, model_type: "stacking" });
    });
    render(<ModelInputPanel />);
    expect(screen.getByText("Stacking")).toBeInTheDocument();
  });

  it("shows each base model's probability when an ensemble is serving", () => {
    act(() => {
      useLiveStore.getState().pushPrediction({
        ...prediction,
        model_type: "stacking",
        base_probabilities: { svm: 0.91, random_forest: 0.86, xgboost: 0.94, mlp: 0.71 },
      });
    });
    render(<ModelInputPanel />);
    expect(screen.getByText("Base models")).toBeInTheDocument();
    for (const label of ["SVM", "RF", "XGB", "MLP"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("hides the base-model block for a single-model prediction", () => {
    act(() => {
      useLiveStore.getState().pushPrediction({ ...prediction, model_type: "svm" });
    });
    render(<ModelInputPanel />);
    expect(screen.queryByText("Base models")).not.toBeInTheDocument();
    expect(screen.getByText("SVM · RBF")).toBeInTheDocument();
  });
});
