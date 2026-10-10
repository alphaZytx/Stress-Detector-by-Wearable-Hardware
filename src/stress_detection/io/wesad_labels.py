"""WESAD label mapping utilities.

WESAD raw label codes (at 700 Hz):
  0 = transient / undefined
  1 = baseline
  2 = stress
  3 = amusement
  4 = meditation
  5, 6, 7 = ignore (not used in public release)

Two mappings are provided:
  - Binary (used for Phase 1.5 baseline training): baseline=0, stress=1.
  - Three-class (stretch goal): low=0 (baseline+meditation), medium=1 (amusement),
    high=2 (stress).

NaN is returned for codes that don't belong in a given scheme. Callers are
expected to drop NaN rows before training.
"""

from __future__ import annotations

import numpy as np


def map_to_binary(label_array: np.ndarray) -> np.ndarray:
    """Map WESAD raw labels to binary stress labels.

    Args:
        label_array: Integer array of raw WESAD label codes.

    Returns:
        Float array: 0.0 = baseline, 1.0 = stress, NaN = drop.
    """
    arr = np.asarray(label_array, dtype=float)
    out = np.full_like(arr, np.nan, dtype=float)
    out[arr == 1] = 0.0  # baseline
    out[arr == 2] = 1.0  # stress
    return out


def map_to_three_class(label_array: np.ndarray) -> np.ndarray:
    """Map WESAD raw labels to three arousal levels.

    Args:
        label_array: Integer array of raw WESAD label codes.

    Returns:
        Float array: 0 = low (baseline/meditation), 1 = medium (amusement),
        2 = high (stress), NaN = drop.
    """
    arr = np.asarray(label_array, dtype=float)
    out = np.full_like(arr, np.nan, dtype=float)
    out[arr == 1] = 0.0  # baseline → low
    out[arr == 4] = 0.0  # meditation → low
    out[arr == 3] = 1.0  # amusement → medium
    out[arr == 2] = 2.0  # stress → high
    return out
