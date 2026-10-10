"""Build features_wesad_v1.parquet by applying the existing feature pipeline to WESAD data.

Loads data/interim/wesad_sensors_clean.parquet, runs each subject through
the same build_feature_table() used for project data, and concatenates.

The output schema is identical to features_v1.parquet plus a subject_id column:
  window_start_ms, window_end_ms, condition, label, subject_id,
  hr_mean, hr_std, hr_min, hr_max, hr_range, hr_slope, hr_pnn_proxy,
  gsr_mean, gsr_std, gsr_min, gsr_max, gsr_range, gsr_slope, gsr_auc, gsr_peaks,
  temp_mean, temp_std, temp_slope
"""

import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stress_detection.config import get_config
from stress_detection.features.pipeline import build_feature_table

_PROJECT_FEATURE_COLS = [
    "window_start_ms", "window_end_ms", "condition", "label",
    "hr_mean", "hr_std", "hr_min", "hr_max", "hr_range", "hr_slope", "hr_pnn_proxy",
    "gsr_mean", "gsr_std", "gsr_min", "gsr_max", "gsr_range", "gsr_slope", "gsr_auc", "gsr_peaks",
    "temp_mean", "temp_std", "temp_slope",
]


def main() -> None:
    cfg = get_config()

    interim_path = cfg.paths.data_interim / "wesad_sensors_clean.parquet"
    if not interim_path.exists():
        logger.error(
            "wesad_sensors_clean.parquet not found. "
            "Run scripts/build_wesad_interim.py first."
        )
        sys.exit(1)

    sensors_df = pd.read_parquet(interim_path)
    subjects = sorted(sensors_df["subject_id"].unique())
    logger.info("Processing %d subjects: %s", len(subjects), subjects)

    all_features = []
    for subject_id in subjects:
        subj_df = sensors_df[sensors_df["subject_id"] == subject_id].reset_index(drop=True)
        feat_df = build_feature_table(subj_df, subject_id=subject_id)
        if feat_df.empty:
            logger.warning("%s: no feature windows produced", subject_id)
            continue
        all_features.append(feat_df)
        n_baseline = (feat_df["condition"] == "baseline").sum()
        n_stress = (feat_df["condition"] == "stress").sum()
        logger.info("%s: %d windows (baseline=%d, stress=%d)",
                    subject_id, len(feat_df), n_baseline, n_stress)

    if not all_features:
        logger.error("No features produced from any subject.")
        sys.exit(1)

    combined = pd.concat(all_features, ignore_index=True)

    # Verify column schema matches features_v1.parquet (plus subject_id)
    expected_cols = set(_PROJECT_FEATURE_COLS) | {"subject_id"}
    actual_cols = set(combined.columns)
    missing = expected_cols - actual_cols
    extra = actual_cols - expected_cols
    if missing:
        logger.error("Missing columns vs features_v1 schema: %s", missing)
        sys.exit(1)
    if extra:
        logger.warning("Extra columns not in features_v1 schema: %s", extra)

    # Reorder: metadata first, then features, then subject_id
    col_order = _PROJECT_FEATURE_COLS + ["subject_id"]
    combined = combined[col_order]

    cfg.paths.data_features.mkdir(parents=True, exist_ok=True)
    out_path = cfg.paths.data_features / "features_wesad_v1.parquet"
    combined.to_parquet(out_path, index=False)

    print("\n=== WESAD Feature Build Summary ===")
    print(f"Total windows:    {len(combined):,}")
    print(f"Subjects:         {len(subjects)}")
    print(f"\nWindows per subject:")
    print(combined.groupby("subject_id").size().to_string())
    print(f"\nWindows per condition:")
    print(combined.groupby("condition").size().to_string())
    print(f"\nFeature columns ({len(_PROJECT_FEATURE_COLS) - 4} + subject_id):")
    print(col_order)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
