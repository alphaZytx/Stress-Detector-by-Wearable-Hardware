"""End-to-end pipeline test on a small synthetic DataFrame."""

import pandas as pd
import pytest

from stress_detection.features.pipeline import build_feature_table

_EXPECTED_META = {"window_start_ms", "window_end_ms", "condition", "label"}
_EXPECTED_FEATURES = {
    "hr_mean", "hr_std", "hr_min", "hr_max", "hr_range", "hr_slope", "hr_pnn_proxy",
    "gsr_mean", "gsr_std", "gsr_min", "gsr_max", "gsr_range", "gsr_slope", "gsr_auc", "gsr_peaks",
    "temp_mean", "temp_std", "temp_slope",
}


def _synthetic_sensors(n_rows=60, condition="baseline") -> pd.DataFrame:
    rows = []
    for i in range(n_rows):
        rows.append({
            "timestamp_ms": i * 1000,
            "bpm": 72.0,
            "avg_bpm": 72.0,
            "bpm_valid": True,
            "temp_c": 36.5,
            "gsr": 100.0,
            "label": condition,
            "condition": condition,
        })
    return pd.DataFrame(rows)


def test_pipeline_output_schema():
    df = _synthetic_sensors(60, "baseline")
    result = build_feature_table(df)

    assert not result.empty
    for col in _EXPECTED_META | _EXPECTED_FEATURES:
        assert col in result.columns, f"Missing column: {col}"


def test_pipeline_two_conditions():
    df = pd.concat([
        _synthetic_sensors(60, "baseline"),
        _synthetic_sensors(60, "stress"),
    ], ignore_index=True)
    result = build_feature_table(df)

    assert set(result["condition"].unique()) == {"baseline", "stress"}


def test_pipeline_condition_label_match():
    df = _synthetic_sensors(60, "baseline")
    result = build_feature_table(df)
    assert (result["label"] == "baseline").all()


def test_pipeline_no_crash_short_df():
    df = _synthetic_sensors(10, "baseline")
    result = build_feature_table(df)
    assert isinstance(result, pd.DataFrame)
