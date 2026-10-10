import numpy as np
import pandas as pd
import pytest

from stress_detection.features.windowing import make_windows


def _make_df(n_rows: int, bpm_valid_all: bool = True, invalid_indices: list[int] | None = None) -> pd.DataFrame:
    """Synthetic 1 Hz sensor DataFrame."""
    rows = []
    for i in range(n_rows):
        rows.append({
            "timestamp_ms": i * 1000,
            "bpm": 70.0,
            "bpm_valid": True,
            "gsr": 100.0,
            "temp_c": 36.5,
            "gx": 0.0, "gy": 0.0, "gz": 0.0,
            "condition": "baseline",
            "label": "baseline",
        })
    df = pd.DataFrame(rows)
    if invalid_indices:
        df.loc[invalid_indices, "bpm_valid"] = False
    return df


def test_60s_window30_stride5_gives_7_windows():
    df = _make_df(60)
    windows = list(make_windows(df, window_s=30, stride_s=5, sampling_hz=1))
    assert len(windows) == 7


def test_window_shorter_than_data_gives_zero():
    df = _make_df(20)
    windows = list(make_windows(df, window_s=30, stride_s=5, sampling_hz=1))
    assert len(windows) == 0


def test_empty_df_gives_zero():
    df = _make_df(0)
    windows = list(make_windows(df, window_s=30, stride_s=5, sampling_hz=1))
    assert len(windows) == 0


def test_window_with_low_bpm_valid_fraction_is_skipped():
    # 60 rows, mark rows 0-29 (first window) as all-invalid bpm
    df = _make_df(60, invalid_indices=list(range(30)))
    # First window (rows 0-29): bpm_valid fraction = 0 < 0.7, should be skipped
    windows = list(make_windows(df, window_s=30, stride_s=5, sampling_hz=1))
    # Without skipping: 7 windows; with first window skipped due to invalid bpm:
    # but stride=5 so windows 1-6 (rows 5-34, 10-39, ...) still overlap with
    # the invalid zone. Let's check that windows with fraction < 0.7 are skipped.
    for start_ms, end_ms, window in windows:
        valid_frac = window["bpm_valid"].mean()
        assert valid_frac >= 0.7, f"Window {start_ms}-{end_ms} has fraction {valid_frac}"


def test_window_yields_correct_timestamps():
    df = _make_df(60)
    windows = list(make_windows(df, window_s=30, stride_s=5, sampling_hz=1))
    start_ms, end_ms, window = windows[0]
    assert start_ms == 0
    assert end_ms == 29000  # last sample in window (index 29, ts=29000)


def test_window_dataframe_length():
    df = _make_df(60)
    windows = list(make_windows(df, window_s=30, stride_s=5, sampling_hz=1))
    for _, _, window in windows:
        assert len(window) == 30
