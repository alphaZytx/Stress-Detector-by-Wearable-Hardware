/**
 * Human-readable metadata for the 18 model-input features.
 *
 * The KEY ORDER here is the canonical training order and MUST match
 * service/features/schema.py FEATURE_COLUMNS - the same order the inference
 * engine feeds the SVM. `featureMeta.test.ts` pins the list so it cannot
 * silently drift from the wire type.
 *
 * Descriptions are written for a viewer reading the dashboard, not for a
 * developer: they say what the number means physiologically, not how it is
 * computed.
 */

import type { FeatureVector } from "@/api/types";

export type FeatureGroupId = "hr" | "gsr" | "temp";

export interface FeatureMeta {
  key: keyof FeatureVector;
  /** Short display name. The raw key is always shown too - it's the real name. */
  label: string;
  group: FeatureGroupId;
  unit: string;
  decimals: number;
  description: string;
}

export const FEATURE_GROUPS: {
  id: FeatureGroupId;
  label: string;
  /** CSS custom property used for the group's accent. */
  colorVar: string;
}[] = [
  { id: "hr", label: "Heart rate", colorVar: "--clinical-danger" },
  { id: "gsr", label: "Skin conductance", colorVar: "--clinical-accent" },
  { id: "temp", label: "Temperature", colorVar: "--clinical-warning" },
];

export const FEATURE_META: FeatureMeta[] = [
  // ---- heart rate (7) ----
  {
    key: "hr_mean",
    label: "Mean",
    group: "hr",
    unit: "bpm",
    decimals: 1,
    description: "Average heart rate across the 30-second window.",
  },
  {
    key: "hr_std",
    label: "Std dev",
    group: "hr",
    unit: "bpm",
    decimals: 2,
    description:
      "How much heart rate varied within the window. Sustained stress tends to flatten this.",
  },
  {
    key: "hr_min",
    label: "Min",
    group: "hr",
    unit: "bpm",
    decimals: 1,
    description: "Lowest heart rate seen in the window.",
  },
  {
    key: "hr_max",
    label: "Max",
    group: "hr",
    unit: "bpm",
    decimals: 1,
    description: "Highest heart rate seen in the window.",
  },
  {
    key: "hr_range",
    label: "Range",
    group: "hr",
    unit: "bpm",
    decimals: 1,
    description: "Max minus min - the spread of heart rate across the window.",
  },
  {
    key: "hr_slope",
    label: "Slope",
    group: "hr",
    unit: "bpm/s",
    decimals: 3,
    description:
      "Trend line through the window. Positive means heart rate is climbing.",
  },
  {
    key: "hr_pnn_proxy",
    label: "HRV proxy",
    group: "hr",
    unit: "",
    decimals: 3,
    description:
      "Stand-in for heart-rate variability: the share of consecutive beats that differ noticeably. Higher usually means calmer.",
  },

  // ---- skin conductance / GSR (8) ----
  {
    key: "gsr_mean",
    label: "Mean",
    group: "gsr",
    unit: "µS-adc",
    decimals: 1,
    description:
      "Average skin conductance. Sweat-gland activity rises with arousal, so this is one of the strongest stress signals.",
  },
  {
    key: "gsr_std",
    label: "Std dev",
    group: "gsr",
    unit: "µS-adc",
    decimals: 2,
    description: "How much skin conductance moved around within the window.",
  },
  {
    key: "gsr_min",
    label: "Min",
    group: "gsr",
    unit: "µS-adc",
    decimals: 1,
    description: "Lowest skin-conductance reading in the window.",
  },
  {
    key: "gsr_max",
    label: "Max",
    group: "gsr",
    unit: "µS-adc",
    decimals: 1,
    description: "Highest skin-conductance reading in the window.",
  },
  {
    key: "gsr_range",
    label: "Range",
    group: "gsr",
    unit: "µS-adc",
    decimals: 1,
    description: "Max minus min - the swing in skin conductance.",
  },
  {
    key: "gsr_slope",
    label: "Slope",
    group: "gsr",
    unit: "µS/s",
    decimals: 3,
    description:
      "Trend line through the window. A rising slope often accompanies a stress response.",
  },
  {
    key: "gsr_auc",
    label: "Area under curve",
    group: "gsr",
    unit: "",
    decimals: 2,
    description:
      "Total area under the z-scored skin-conductance curve - cumulative arousal over the window.",
  },
  {
    key: "gsr_peaks",
    label: "Peaks",
    group: "gsr",
    unit: "count",
    decimals: 0,
    description:
      "Number of distinct skin-conductance responses - discrete bursts of sweat-gland activity.",
  },

  // ---- temperature (3) ----
  {
    key: "temp_mean",
    label: "Mean",
    group: "temp",
    unit: "°C",
    decimals: 2,
    description: "Average skin temperature across the window.",
  },
  {
    key: "temp_std",
    label: "Std dev",
    group: "temp",
    unit: "°C",
    decimals: 3,
    description: "How much skin temperature drifted within the window.",
  },
  {
    key: "temp_slope",
    label: "Slope",
    group: "temp",
    unit: "°C/s",
    decimals: 4,
    description:
      "Trend line through the window. Peripheral temperature often dips under acute stress.",
  },
];

/** Canonical feature order - mirrors FEATURE_COLUMNS in the backend schema. */
export const FEATURE_KEYS = FEATURE_META.map((f) => f.key);

export const FEATURE_META_BY_KEY = Object.fromEntries(
  FEATURE_META.map((f) => [f.key, f]),
) as Record<keyof FeatureVector, FeatureMeta>;

export function metaForGroup(group: FeatureGroupId): FeatureMeta[] {
  return FEATURE_META.filter((f) => f.group === group);
}
