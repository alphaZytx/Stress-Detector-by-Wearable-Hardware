"""Per-window feature extractors for the 1 Hz sensor stream.

Each function takes a window DataFrame and returns dict[str, float].
All keys are already prefixed with their group (hr_, gsr_, temp_).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

logger = logging.getLogger(__name__)

_NAN_DICT = lambda keys: {k: float("nan") for k in keys}

_HR_KEYS = [
    "hr_mean", "hr_std", "hr_min", "hr_max",
    "hr_range", "hr_slope", "hr_pnn_proxy",
]

_GSR_KEYS = [
    "gsr_mean", "gsr_std", "gsr_min", "gsr_max",
    "gsr_range", "gsr_slope", "gsr_auc", "gsr_peaks",
]

_TEMP_KEYS = ["temp_mean", "temp_std", "temp_slope"]


# Minimum prominence for GSR peak detection, applied to the *z-score normalised*
# GSR signal within each window. Working in z-score space makes peak detection
# unit-invariant: it fires the same way on raw 12-bit ADC values (project
# hardware) and on small µS EDA values (WESAD), where the previous absolute
# prominence of 3 detected ~zero peaks and collapsed the feature to a constant.
# 0.5 = half a standard deviation, which catches moderate skin-conductance
# responses without firing on noise.
_GSR_PEAK_PROMINENCE = 0.5


def _slope(values: np.ndarray, times: np.ndarray) -> float:
    """Return linear fit slope of values over times. Returns nan if <2 points."""
    if len(values) < 2:
        return float("nan")
    coeffs = np.polyfit(times, values, 1)
    return float(coeffs[0])


def extract_hr_features(window: pd.DataFrame) -> dict[str, float]:
    """Heart rate features from valid BPM samples in the window.

    Source: bpm column (rows where bpm_valid == True only).
    Returns all-NaN dict if fewer than 5 valid samples.
    """
    valid = window.loc[window["bpm_valid"] == True, "bpm"].dropna()

    if len(valid) < 5:
        return _NAN_DICT(_HR_KEYS)

    times = np.arange(len(valid), dtype=float)
    vals = valid.to_numpy(dtype=float)
    diffs = np.abs(np.diff(vals))

    return {
        "hr_mean": float(np.mean(vals)),
        "hr_std": float(np.std(vals, ddof=1)),
        "hr_min": float(np.min(vals)),
        "hr_max": float(np.max(vals)),
        "hr_range": float(np.max(vals) - np.min(vals)),
        "hr_slope": _slope(vals, times),
        "hr_pnn_proxy": float(np.mean(diffs > 5)) if len(diffs) > 0 else float("nan"),
    }


def extract_gsr_features(window: pd.DataFrame) -> dict[str, float]:
    """Galvanic skin response features from the window.

    Source: gsr column.
    gsr_peaks: count of skin-conductance response peaks. The GSR signal is
    z-score normalised within the window *before* peak detection, then
    scipy.signal.find_peaks is run with prominence=0.5 (half a standard
    deviation). Working in z-score space makes the peak count unit-invariant:
    identical peak structure produces the same count whether the input is raw
    12-bit ADC (project hardware, values ~100) or µS EDA (WESAD, values ~1).
    The previous absolute prominence of 3 fired on ADC scale but detected
    ~zero peaks on µS data, collapsing the feature to a constant for WESAD.
    If the window has <5 samples or near-zero variance, gsr_peaks = 0.
    gsr_auc: trapezoidal area under the GSR curve (proportional to arousal load).
    """
    vals = window["gsr"].to_numpy(dtype=float)
    times = np.arange(len(vals), dtype=float)

    gsr_clean = window["gsr"].dropna().to_numpy(dtype=float)
    if len(gsr_clean) < 5 or gsr_clean.std() < 1e-9:
        n_peaks = 0
    else:
        gsr_z = (gsr_clean - gsr_clean.mean()) / gsr_clean.std()
        peaks, _ = find_peaks(gsr_z, prominence=_GSR_PEAK_PROMINENCE)
        n_peaks = len(peaks)

    return {
        "gsr_mean": float(np.mean(vals)),
        "gsr_std": float(np.std(vals, ddof=1)) if len(vals) > 1 else float("nan"),
        "gsr_min": float(np.min(vals)),
        "gsr_max": float(np.max(vals)),
        "gsr_range": float(np.max(vals) - np.min(vals)),
        "gsr_slope": _slope(vals, times),
        "gsr_auc": float(np.trapezoid(vals, times)),
        "gsr_peaks": float(n_peaks),
    }


def extract_temp_features(window: pd.DataFrame) -> dict[str, float]:
    """Skin temperature features from the window.

    Source: temp_c column. Kept minimal - temperature drifts slowly.
    """
    vals = window["temp_c"].to_numpy(dtype=float)
    times = np.arange(len(vals), dtype=float)

    return {
        "temp_mean": float(np.mean(vals)),
        "temp_std": float(np.std(vals, ddof=1)) if len(vals) > 1 else float("nan"),
        "temp_slope": _slope(vals, times),
    }

