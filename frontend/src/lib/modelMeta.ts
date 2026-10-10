/**
 * Display metadata for the classifier the service is serving.
 *
 * The backend sends `model_type` on every prediction (see
 * service/inference/engine.py). It is optional on the wire so payloads from an
 * older backend still parse; when it is absent the UI falls back to the SVM
 * baseline, which is what such a backend would have been running.
 */

import type { ModelType, Prediction } from "@/api/types";

export const MODEL_LABELS: Record<string, string> = {
  svm: "SVM · RBF",
  random_forest: "Random Forest",
  xgboost: "XGBoost",
  mlp: "MLP · 64/32/16",
  soft_voting: "Soft Voting",
  stacking: "Stacking",
};

/** Short names for the per-base-model readout inside an ensemble. */
export const BASE_MODEL_LABELS: Record<string, string> = {
  svm: "SVM",
  random_forest: "RF",
  xgboost: "XGB",
  mlp: "MLP",
};

/** Canonical base-model order - matches models/common.py BASE_MODEL_NAMES. */
export const BASE_MODEL_ORDER = ["svm", "random_forest", "xgboost", "mlp"];

export function modelLabel(modelType: ModelType | string | undefined): string {
  if (!modelType) return MODEL_LABELS.svm;
  return MODEL_LABELS[modelType] ?? modelType;
}

export function isEnsemble(modelType: ModelType | string | undefined): boolean {
  return modelType === "soft_voting" || modelType === "stacking";
}

/**
 * Per-base-model probabilities in canonical order, or null when a single model
 * is serving (which sends no base probabilities).
 */
export function baseProbabilities(
  prediction: Prediction | null,
): { key: string; label: string; value: number }[] | null {
  const probs = prediction?.base_probabilities;
  if (!probs) return null;
  const keys = [
    ...BASE_MODEL_ORDER.filter((k) => k in probs),
    ...Object.keys(probs).filter((k) => !BASE_MODEL_ORDER.includes(k)),
  ];
  if (keys.length === 0) return null;
  return keys.map((key) => ({
    key,
    label: BASE_MODEL_LABELS[key] ?? key,
    value: probs[key],
  }));
}
