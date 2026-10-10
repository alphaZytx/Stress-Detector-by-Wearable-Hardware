"""Canonical feature schema for the three-sensor, 18-feature model.

This is the single source of truth for feature ordering across the live service
(streamer emits in this order; inference engine feeds the model in this order).
It MUST match the feature columns of features_v1.parquet / features_wesad_v1.parquet
(metadata columns excluded), in the same order produced by
stress_detection.features.pipeline.build_feature_table().

A test (test_streamer.py) verifies this list against the on-disk parquet so it
cannot silently drift.
"""

from __future__ import annotations

FEATURE_COLUMNS: list[str] = [
    "hr_mean", "hr_std", "hr_min", "hr_max", "hr_range", "hr_slope", "hr_pnn_proxy",
    "gsr_mean", "gsr_std", "gsr_min", "gsr_max", "gsr_range", "gsr_slope",
    "gsr_auc", "gsr_peaks",
    "temp_mean", "temp_std", "temp_slope",
]

# Metadata columns build_feature_table() emits alongside the features.
META_COLUMNS: set[str] = {
    "window_start_ms", "window_end_ms", "condition", "label", "subject_id",
}
