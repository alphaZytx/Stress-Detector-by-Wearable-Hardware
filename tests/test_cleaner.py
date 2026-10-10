import numpy as np
import pandas as pd
import pytest

from stress_detection.io.cleaner import clean_sensors
from stress_detection.io.loader import load_sensors

# ── sensor cleaner ─────────────────────────────────────────────────────────────

def _make_sensor_df(rows):
    """Build a minimal sensor DataFrame for testing."""
    cols = [
        "timestamp_ms", "bpm", "avg_bpm", "temp_c", "gsr",
        "label", "condition",
    ]
    return pd.DataFrame(rows, columns=cols)


def test_clean_sensors_drops_warmup():
    df = _make_sensor_df([
        [0, 60.0, 60.0, 0.0, 100, "baseline", "baseline"],
        [1000, 65.0, 65.0, 0.0, 100, "baseline", "baseline"],
        [2000, 70.0, 70.0, 36.5, 100, "baseline", "baseline"],
    ])
    cleaned = clean_sensors(df)
    assert len(cleaned) == 1
    assert (cleaned["temp_c"] != 0).all()


def test_clean_sensors_invalid_bpm_not_dropped():
    df = _make_sensor_df([
        [0, 30.0, 30.0, 36.5, 100, "baseline", "baseline"],
        [1000, 75.0, 75.0, 36.5, 100, "baseline", "baseline"],
        [2000, 210.0, 200.0, 36.5, 100, "baseline", "baseline"],
    ])
    cleaned = clean_sensors(df)
    assert len(cleaned) == 3, "invalid bpm rows must NOT be dropped"
    assert pd.isna(cleaned.loc[0, "bpm"]), "bpm=30 should be NaN"
    assert cleaned.loc[1, "bpm"] == 75.0
    assert pd.isna(cleaned.loc[2, "bpm"]), "bpm=210 should be NaN"
    assert cleaned.loc[0, "bpm_valid"] is False or cleaned.loc[0, "bpm_valid"] == False
    assert cleaned.loc[1, "bpm_valid"] is True or cleaned.loc[1, "bpm_valid"] == True


def test_clean_sensors_bpm_valid_column_exists():
    df = load_sensors("baseline")
    cleaned = clean_sensors(df)
    assert "bpm_valid" in cleaned.columns


def test_clean_sensors_real_data_drops_warmup():
    df = load_sensors("baseline")
    cleaned = clean_sensors(df)
    assert (cleaned["temp_c"] != 0).all()
    assert len(cleaned) < len(df)


# ── parquet round-trip ─────────────────────────────────────────────────────────

def test_sensors_parquet_roundtrip(tmp_path):
    df = load_sensors("baseline")
    cleaned = clean_sensors(df)
    p = tmp_path / "sensors.parquet"
    cleaned.to_parquet(p, index=False)
    reloaded = pd.read_parquet(p)
    pd.testing.assert_frame_equal(cleaned.reset_index(drop=True), reloaded)
