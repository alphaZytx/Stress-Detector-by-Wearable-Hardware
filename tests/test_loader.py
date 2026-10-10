import pandas as pd
import pytest

from stress_detection.io.loader import load_sensors

SENSOR_COLS = [
    "timestamp_ms", "bpm", "avg_bpm", "temp_c", "gsr",
    "label", "condition",
]


@pytest.mark.parametrize("condition", ["baseline", "stress"])
def test_load_sensors_schema(condition):
    df = load_sensors(condition)
    assert list(df.columns) == SENSOR_COLS
    assert (df["condition"] == condition).all()
    assert len(df) > 0


@pytest.mark.parametrize("condition", ["baseline", "stress"])
def test_load_sensors_keeps_only_three_sensor_channels(condition):
    df = load_sensors(condition)
    assert set(df.columns) == set(SENSOR_COLS)
