"""Sliding-window utilities for the 1 Hz sensor stream.

Window math (for reference):
  With 298 s of data at 1 Hz, window=30 s, stride=5 s:
    n_windows = floor((298 - 30) / 5) + 1 = 54 windows per condition

  For the 296-row cleaned data the count may be 53 or 54 depending on
  exact timestamp coverage; both are expected.
"""

from __future__ import annotations

import logging
from typing import Iterator

import pandas as pd

logger = logging.getLogger(__name__)


def make_windows(
    df: pd.DataFrame,
    window_s: int,
    stride_s: int,
    sampling_hz: int,
    timestamp_col: str = "timestamp_ms",
) -> Iterator[tuple[int, int, pd.DataFrame]]:
    """Yield (window_start_ms, window_end_ms, window_df) for sliding windows.

    Windows where the fraction of bpm_valid==True rows is below
    min_valid_bpm_fraction (from config) are silently skipped.

    Args:
        df: Sensor DataFrame with timestamp_col and bpm_valid columns.
        window_s: Window length in seconds.
        stride_s: Stride in seconds.
        sampling_hz: Sampling rate (1 for the sensor file).
        timestamp_col: Column holding millisecond timestamps.

    Yields:
        Tuples of (start_ms, end_ms, window_dataframe).
    """
    from stress_detection.config import get_config

    min_valid_frac = get_config().windowing.min_valid_bpm_fraction

    window_rows = window_s * sampling_hz
    stride_rows = stride_s * sampling_hz
    n = len(df)

    start = 0
    while start + window_rows <= n:
        end = start + window_rows
        window = df.iloc[start:end].copy()

        if "bpm_valid" in window.columns:
            valid_frac = window["bpm_valid"].mean()
            if valid_frac < min_valid_frac:
                logger.debug(
                    "Skipping window [%d:%d]: bpm_valid fraction %.2f < %.2f",
                    start, end, valid_frac, min_valid_frac,
                )
                start += stride_rows
                continue

        start_ms = int(window[timestamp_col].iloc[0])
        end_ms = int(window[timestamp_col].iloc[-1])
        yield start_ms, end_ms, window
        start += stride_rows
