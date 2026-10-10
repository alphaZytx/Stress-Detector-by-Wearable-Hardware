"""Cleaning functions for three-sensor wearable DataFrames.

These operate on DataFrames produced by loader.py.
No imputation is performed - invalid values are flagged or dropped,
but row alignment is preserved wherever possible.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_BPM_LOW = 40
_BPM_HIGH = 200


def clean_sensors(df: pd.DataFrame) -> pd.DataFrame:
    """Clean a sensors DataFrame loaded by load_sensors().

    Steps:
    1. Drop rows where temp_c == 0 (temperature sensor warmup/invalid reading).
    2. Add bpm_valid bool column: False where bpm is outside [40, 200].
       Set bpm to NaN for those rows - row is kept for other channel alignment.
    """
    df = df.copy()

    before = len(df)
    df = df[df["temp_c"] != 0].reset_index(drop=True)
    dropped_warmup = before - len(df)
    logger.debug("clean_sensors: dropped %d warmup rows (temp_c==0)", dropped_warmup)

    invalid_mask = (df["bpm"] < _BPM_LOW) | (df["bpm"] > _BPM_HIGH)
    df["bpm_valid"] = ~invalid_mask
    df.loc[invalid_mask, "bpm"] = np.nan
    logger.debug(
        "clean_sensors: flagged %d invalid bpm rows (outside [%d, %d])",
        invalid_mask.sum(), _BPM_LOW, _BPM_HIGH,
    )

    return df
