/**
 * The 18 features, grouped by the signal they summarise.
 *
 * Order within each group, and the groups' order, follow FEATURE_COLUMNS in
 * service/features/schema.py - the canonical model-input contract. Grouping is
 * presentational only; it never reorders what the model receives.
 */

export interface FeatureGroup {
  title: string;
  keys: string[];
}

export const FEATURE_GROUPS: FeatureGroup[] = [
  {
    title: "Heart rate",
    keys: [
      "hr_mean",
      "hr_std",
      "hr_min",
      "hr_max",
      "hr_range",
      "hr_slope",
      "hr_pnn_proxy",
    ],
  },
  {
    title: "Skin conductance",
    keys: [
      "gsr_mean",
      "gsr_std",
      "gsr_min",
      "gsr_max",
      "gsr_range",
      "gsr_slope",
      "gsr_auc",
      "gsr_peaks",
    ],
  },
  {
    title: "Temperature",
    keys: ["temp_mean", "temp_std", "temp_slope"],
  },
];

/** Sanity: the three groups must cover exactly the 18 contract columns. */
export const FEATURE_COUNT = FEATURE_GROUPS.reduce(
  (n, g) => n + g.keys.length,
  0,
);
