"""Raw CSV loader for the three-sensor wearable data.

Each loader reads one condition file, applies minimal structural transforms
(renames, column selection, condition tag), and returns a typed DataFrame.
No cleaning is done here - see cleaner.py.
"""

from __future__ import annotations

import logging
from typing import Literal

import pandas as pd

from stress_detection.config import get_config

logger = logging.getLogger(__name__)

_SENSOR_KEEP = [
    "timestamp_ms",
    "bpm",
    "avg_bpm",
    "temp_c",
    "gsr",
    "label",
    "condition",
]

_SENSOR_FILES = {
    "baseline": "revised_sensors_baseline__1_.csv",
    "stress": "revised_sensors_stress__1_.csv",
}


def load_sensors(condition: Literal["baseline", "stress"]) -> pd.DataFrame:
    """Load one multi-sensor recording and return a clean-schema DataFrame.

    Output columns: timestamp_ms, bpm, avg_bpm, temp_c, gsr, label, condition.
    """
    cfg = get_config()
    path = cfg.paths.data_raw / _SENSOR_FILES[condition]
    df = pd.read_csv(path)
    df = df.rename(columns={"timestamp": "timestamp_ms"})
    df["condition"] = condition
    df = df[_SENSOR_KEEP]
    logger.debug("load_sensors(%s): %d rows", condition, len(df))
    return df
