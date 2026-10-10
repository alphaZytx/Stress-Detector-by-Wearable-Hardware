import { describe, expect, it } from "vitest";
import {
  BASE_MODEL_ORDER,
  baseProbabilities,
  isEnsemble,
  modelLabel,
} from "@/lib/modelMeta";
import type { Prediction } from "@/api/types";

function makePrediction(overrides: Partial<Prediction> = {}): Prediction {
  return {
    timestamp_ms: 1000,
    label: "stress",
    confidence: 0.82,
    smoothed_label: "stress",
    smoothed_confidence: 0.77,
    raw_proba: { baseline: 0.18, stress: 0.82 },
    calibration_applied: false,
    ...overrides,
  };
}

describe("modelLabel", () => {
  it("names each supported model type", () => {
    expect(modelLabel("svm")).toBe("SVM · RBF");
    expect(modelLabel("random_forest")).toBe("Random Forest");
    expect(modelLabel("xgboost")).toBe("XGBoost");
    expect(modelLabel("mlp")).toBe("MLP · 64/32/16");
    expect(modelLabel("soft_voting")).toBe("Soft Voting");
    expect(modelLabel("stacking")).toBe("Stacking");
  });

  it("falls back to the SVM baseline when the backend sends no model_type", () => {
    expect(modelLabel(undefined)).toBe("SVM · RBF");
  });

  it("passes an unknown type through rather than dropping it", () => {
    expect(modelLabel("something_new")).toBe("something_new");
  });
});

describe("isEnsemble", () => {
  it("is true only for the two ensemble strategies", () => {
    expect(isEnsemble("stacking")).toBe(true);
    expect(isEnsemble("soft_voting")).toBe(true);
    expect(isEnsemble("svm")).toBe(false);
    expect(isEnsemble(undefined)).toBe(false);
  });
});

describe("baseProbabilities", () => {
  it("returns null for a single-model prediction", () => {
    expect(baseProbabilities(makePrediction())).toBeNull();
    expect(baseProbabilities(makePrediction({ base_probabilities: null }))).toBeNull();
    expect(baseProbabilities(null)).toBeNull();
  });

  it("returns the four base models in canonical order", () => {
    const prediction = makePrediction({
      model_type: "stacking",
      // Deliberately out of order on the wire.
      base_probabilities: { mlp: 0.71, svm: 0.91, xgboost: 0.94, random_forest: 0.86 },
    });
    const rows = baseProbabilities(prediction);
    expect(rows?.map((r) => r.key)).toEqual(BASE_MODEL_ORDER);
    expect(rows?.map((r) => r.label)).toEqual(["SVM", "RF", "XGB", "MLP"]);
    expect(rows?.map((r) => r.value)).toEqual([0.91, 0.86, 0.94, 0.71]);
  });

  it("keeps unknown base models instead of silently dropping them", () => {
    const rows = baseProbabilities(
      makePrediction({ base_probabilities: { svm: 0.5, future_model: 0.4 } }),
    );
    expect(rows?.map((r) => r.key)).toEqual(["svm", "future_model"]);
  });

  it("treats an empty map as no ensemble data", () => {
    expect(baseProbabilities(makePrediction({ base_probabilities: {} }))).toBeNull();
  });
});
