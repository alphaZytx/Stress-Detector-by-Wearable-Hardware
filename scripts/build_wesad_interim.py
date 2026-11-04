"""Build wesad_sensors_clean.parquet from raw WESAD subject pickles.

For each WESAD subject:
  1. Load the per-subject pickle (data/wesad/raw/SX/SX.pkl).
  2. Resample all signals to 1 Hz (see src/stress_detection/io/wesad.py for mapping decisions).
  3. Map raw WESAD labels to binary (0=baseline, 1=stress); drop unlabelled rows.
  4. Add string label/condition columns matching the sensors_clean.parquet schema.

Output: data/interim/wesad_sensors_clean.parquet

Schema matches sensors_clean.parquet exactly, with an additional subject_id column:
  timestamp_ms, bpm, avg_bpm, temp_c, gsr, label, condition, subject_id, bpm_valid

Two display-only compatibility columns are also added:
  spo2          : fixed at 98.0 (WESAD has no SpO2 channel)
  ambient_temp_c: deterministic neutral synthetic room temperature

Neither column is used by build_wesad_features.py or by the classifier.
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stress_detection.config import get_config
from stress_detection.io.wesad import WESAD_SUBJECTS, load_wesad_subject, build_wesad_1hz
from stress_detection.io.wesad_labels import map_to_binary

_LABEL_MAP = {0.0: "baseline", 1.0: "stress"}


def process_subject(subject_id: str, cfg) -> pd.DataFrame | None:
    pkl_path = cfg.paths.data_wesad_raw / subject_id / f"{subject_id}.pkl"
    if not pkl_path.exists():
        logger.warning("Skipping %s: file not found at %s", subject_id, pkl_path)
        return None

    try:
        subj_dict = load_wesad_subject(subject_id)
    except Exception as exc:
        logger.error("Failed to load %s: %s", subject_id, exc)
        return None

    df = build_wesad_1hz(subj_dict)

    # Map raw integer label codes to binary float (0=baseline, 1=stress, NaN=drop)
    binary_labels = map_to_binary(df["label_code"].to_numpy())
    df["binary_label"] = binary_labels

    # Drop rows with NaN label (transient, amusement, meditation)
    before = len(df)
    df = df[~np.isnan(df["binary_label"])].copy()
    after = len(df)
    dropped = before - after
    if dropped:
        logger.info("%s: dropped %d rows with undefined labels (%.1f%%)",
                    subject_id, dropped, 100 * dropped / before)

    # Build string label/condition columns to match sensors_clean.parquet schema
    df["label"] = df["binary_label"].map(_LABEL_MAP)
    df["condition"] = df["label"]

    # Auxiliary hardware-schema values only. Keep them independent of the
    # stress label so they cannot introduce a synthetic shortcut. WESAD's real
    # wrist TEMP remains the model's temp_c input.
    df["spo2"] = 98.0
    seconds = df["timestamp_ms"].to_numpy(dtype=float) / 1000.0
    subject_number = int(subject_id.removeprefix("S"))
    df["ambient_temp_c"] = (
        24.0 + 0.25 * np.sin(seconds / 900.0 + subject_number)
    )

    df = df.drop(columns=["label_code", "binary_label"])

    n_baseline = (df["label"] == "baseline").sum()
    n_stress = (df["label"] == "stress").sum()
    logger.info("%s: %d rows total - baseline=%d  stress=%d",
                subject_id, len(df), n_baseline, n_stress)

    return df


def main() -> None:
    cfg = get_config()
    cfg.paths.data_interim.mkdir(parents=True, exist_ok=True)

    all_dfs = []
    failed = []

    for subject_id in WESAD_SUBJECTS:
        df = process_subject(subject_id, cfg)
        if df is not None and len(df) > 0:
            all_dfs.append(df)
        elif df is None:
            failed.append(subject_id)

    if not all_dfs:
        logger.error(
            "No subjects loaded. Run scripts/download_wesad.py first, "
            "or manually populate data/wesad/raw/."
        )
        sys.exit(1)

    combined = pd.concat(all_dfs, ignore_index=True)

    # Reorder columns to match sensors_clean.parquet schema (+ subject_id at end)
    ordered_cols = [
        "timestamp_ms", "bpm", "avg_bpm", "temp_c", "gsr",
        "spo2", "ambient_temp_c", "label", "condition", "subject_id", "bpm_valid",
    ]
    combined = combined[ordered_cols]

    out_path = cfg.paths.data_interim / "wesad_sensors_clean.parquet"
    combined.to_parquet(out_path, index=False)

    print("\n=== WESAD Interim Build Summary ===")
    print(f"Subjects loaded:  {len(all_dfs)} / {len(WESAD_SUBJECTS)}")
    if failed:
        print(f"Subjects skipped: {failed}")
    print(f"Total rows:       {len(combined):,}")
    print(f"Label distribution:\n{combined['label'].value_counts()}")
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
