"""Feature extraction pipeline: sensor DataFrame → windowed feature table.

Output schema (one row per window):
  window_start_ms   int      - timestamp of first sample in window
  window_end_ms     int      - timestamp of last sample in window
  condition         str      - "baseline" or "stress"
  label             str      - majority label within window (always = condition here)
  hr_mean           float    - mean BPM of valid samples
  hr_std            float    - std BPM
  hr_min            float    - min BPM
  hr_max            float    - max BPM
  hr_range          float    - max - min BPM
  hr_slope          float    - linear trend slope (BPM / sample)
  hr_pnn_proxy      float    - fraction of consecutive |diff| > 5 BPM
  gsr_mean          float    - mean GSR
  gsr_std           float    - std GSR
  gsr_min           float    - min GSR
  gsr_max           float    - max GSR
  gsr_range         float    - max - min GSR
  gsr_slope         float    - linear trend slope (GSR / sample)
  gsr_auc           float    - trapezoidal area under GSR curve
  gsr_peaks         float    - count of GSR peaks (z-score normalised, prominence >= 0.5)
  temp_mean         float    - mean skin temperature (°C)
  temp_std          float    - std temperature
  temp_slope        float    - linear temperature trend
"""

from __future__ import annotations

import logging

import pandas as pd

from stress_detection.config import get_config
from stress_detection.features.extractors import (
    extract_gsr_features,
    extract_hr_features,
    extract_temp_features,
)
from stress_detection.features.windowing import make_windows

logger = logging.getLogger(__name__)


def _majority_label(window: pd.DataFrame) -> str:
    """Return the most common label value in a window."""
    if "label" not in window.columns:
        return "unknown"
    counts = window["label"].value_counts()
    return str(counts.index[0]) if len(counts) else "unknown"


def build_feature_table(
    sensors_df: pd.DataFrame,
    subject_id: str | None = None,
) -> pd.DataFrame:
    """Build one-row-per-window feature table from cleaned sensor data.

    Args:
        sensors_df: Output of clean_sensors(), may contain both conditions.
        subject_id: Optional identifier added as a column (used by WESAD pipeline).

    Returns:
        DataFrame with schema documented at the top of this module.
        If subject_id is provided, a 'subject_id' column is appended.
    """
    cfg = get_config()
    rows = []

    for condition in sensors_df["condition"].unique():
        cond_df = sensors_df[sensors_df["condition"] == condition].reset_index(drop=True)

        windows = list(
            make_windows(
                cond_df,
                window_s=cfg.windowing.window_s,
                stride_s=cfg.windowing.stride_s,
                sampling_hz=cfg.sampling.sensors_hz,
            )
        )
        logger.info("%s: %d windows", condition, len(windows))

        for start_ms, end_ms, window in windows:
            feats: dict = {}
            feats.update(extract_hr_features(window))
            feats.update(extract_gsr_features(window))
            feats.update(extract_temp_features(window))

            feats["window_start_ms"] = start_ms
            feats["window_end_ms"] = end_ms
            feats["condition"] = condition
            feats["label"] = _majority_label(window)
            if subject_id is not None:
                feats["subject_id"] = subject_id

            rows.append(feats)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # put metadata columns first
    meta_cols = ["window_start_ms", "window_end_ms", "condition", "label"]
    feat_cols = [c for c in df.columns if c not in meta_cols]
    df = df[meta_cols + feat_cols]

    return df
