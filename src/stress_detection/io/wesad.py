"""WESAD dataset loader.

Loads per-subject pickle files from the WESAD wrist sensor dataset and returns
typed DataFrames matching the project's 1 Hz sensor stream schema.

Hardware mapping (wrist-only):
  We map the three signals available on the wearable: MAX30105-compatible BVP,
  GSR/EDA, and MLX90614-compatible temperature. Other WESAD signals are ignored.

Signal mapping decisions:
  bpm       : Derived from wrist BVP (64 Hz) via peak detection (see below).
  gsr       : wrist EDA (4 Hz) resampled to 1 Hz by mean. WESAD EDA is in µS;
              project GSR is raw ADC. Units differ intentionally - StandardScaler
              in the SVM pipeline normalises both datasets independently.
  temp_c    : wrist TEMP (4 Hz) resampled to 1 Hz by mean.

BVP → BPM derivation:
  1. Find peaks in BVP at 64 Hz using scipy.signal.find_peaks with
     min_distance = 0.3 s * 64 Hz = 19 samples.
  2. Compute RR intervals (seconds) between consecutive peaks.
  3. Reject implausible intervals: RR < 0.3 s (>200 BPM) or RR > 2 s (<30 BPM).
  4. For each 1-second bin, assign the median BPM of all valid peaks
     whose second peak falls in that bin. If no valid peaks, bpm = NaN.

Pickle quirk:
  WESAD pickles were written with Python 2's cPickle. Open with
  encoding='latin1' to avoid UnicodeDecodeError on string keys.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

from stress_detection.config import get_config

logger = logging.getLogger(__name__)

# S1 and S12 do not exist in the public WESAD release.
WESAD_SUBJECTS = [
    "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9",
    "S10", "S11", "S13", "S14", "S15", "S16", "S17",
]

_BVP_HZ = 64
_EDA_HZ = 4
_TEMP_HZ = 4
_LABEL_HZ = 700
_MIN_RR_S = 0.3   # < 0.3 s → >200 BPM, reject
_MAX_RR_S = 2.0   # > 2.0 s → <30 BPM, reject
_BPM_VALID_LO = 40
_BPM_VALID_HI = 200


def load_wesad_subject(
    subject_id: str,
    data_dir: Path | None = None,
) -> dict:
    """Load a WESAD subject pickle and return a typed signal dict.

    Args:
        subject_id: One of WESAD_SUBJECTS (e.g. "S2").
        data_dir: Override the default data/wesad/raw/ directory (used in tests).

    Returns:
        dict with keys:
            subject_id : str
            wrist_bvp  : pd.Series  (64 Hz)
            wrist_eda  : pd.Series  (4 Hz)
            wrist_temp : pd.Series  (4 Hz)
            label      : pd.Series  (700 Hz, raw integer codes)
    """
    if data_dir is None:
        cfg = get_config()
        data_dir = cfg.paths.data_wesad_raw

    pkl_path = Path(data_dir) / subject_id / f"{subject_id}.pkl"
    if not pkl_path.exists():
        raise FileNotFoundError(
            f"WESAD pickle not found: {pkl_path}\n"
            "Run scripts/download_wesad.py or manually place per-subject "
            "folders in data/wesad/raw/."
        )

    with open(pkl_path, "rb") as f:
        data = pickle.load(f, encoding="latin1")

    wrist = data["signal"]["wrist"]

    bvp = pd.Series(wrist["BVP"].flatten(), name="bvp")
    eda = pd.Series(wrist["EDA"].flatten(), name="eda")
    temp = pd.Series(wrist["TEMP"].flatten(), name="temp")
    label = pd.Series(data["label"].flatten().astype(int), name="label")

    logger.info(
        "%s: BVP=%d, EDA=%d, TEMP=%d, label=%d",
        subject_id, len(bvp), len(eda), len(temp), len(label),
    )

    return {
        "subject_id": subject_id,
        "wrist_bvp": bvp,
        "wrist_eda": eda,
        "wrist_temp": temp,
        "label": label,
    }


def _bvp_to_bpm_1hz(bvp: pd.Series, n_seconds: int) -> np.ndarray:
    """Derive 1 Hz BPM array from a 64 Hz BVP signal via peak detection."""
    vals = bvp.to_numpy(dtype=float)
    min_dist = int(_MIN_RR_S * _BVP_HZ)  # 19 samples
    peaks, _ = find_peaks(vals, distance=min_dist)

    if len(peaks) < 2:
        return np.full(n_seconds, np.nan)

    peak_times_s = peaks / _BVP_HZ
    rr_s = np.diff(peak_times_s)
    bpm_vals = 60.0 / rr_s

    # Reject implausible beats
    valid = (rr_s >= _MIN_RR_S) & (rr_s <= _MAX_RR_S)
    bpm_vals[~valid] = np.nan

    # Second peak of each RR pair → assign to its 1-second bin
    second_peak_times = peak_times_s[1:]
    beat_bin = np.floor(second_peak_times).astype(int)

    bpm_1hz = np.full(n_seconds, np.nan)
    for sec in range(n_seconds):
        mask = (beat_bin == sec) & valid
        if mask.any():
            bpm_1hz[sec] = np.nanmedian(bpm_vals[mask])

    return bpm_1hz


def _resample_to_1hz_mean(signal: np.ndarray, hz: int, n_seconds: int) -> np.ndarray:
    """Downsample a signal at `hz` to 1 Hz by taking the mean per second."""
    out = np.full(n_seconds, np.nan)
    for sec in range(n_seconds):
        start = sec * hz
        end = start + hz
        chunk = signal[start:end]
        if len(chunk) > 0:
            out[sec] = np.mean(chunk)
    return out


def _label_mode_1hz(label: np.ndarray, hz: int, n_seconds: int) -> np.ndarray:
    """Downsample integer label array at `hz` to 1 Hz by taking the mode per second."""
    from scipy.stats import mode as scipy_mode

    out = np.zeros(n_seconds, dtype=int)
    for sec in range(n_seconds):
        start = sec * hz
        end = start + hz
        chunk = label[start:end]
        if len(chunk) > 0:
            result = scipy_mode(chunk, keepdims=True)
            out[sec] = int(result.mode[0])
    return out


def build_wesad_1hz(subject_dict: dict) -> pd.DataFrame:
    """Convert a loaded WESAD subject dict to a 1 Hz sensor DataFrame.

    The output schema matches sensors_clean.parquet plus a subject_id column.
    Schema: timestamp_ms, bpm, avg_bpm, temp_c, gsr, label, condition,
            subject_id, bpm_valid
    """
    subject_id = subject_dict["subject_id"]
    bvp = subject_dict["wrist_bvp"]
    eda = subject_dict["wrist_eda"]
    temp = subject_dict["wrist_temp"]
    label_raw = subject_dict["label"]

    # Duration is governed by the shortest signal
    n_seconds = min(
        len(bvp) // _BVP_HZ,
        len(eda) // _EDA_HZ,
        len(temp) // _TEMP_HZ,
        len(label_raw) // _LABEL_HZ,
    )

    bpm_arr = _bvp_to_bpm_1hz(bvp, n_seconds)

    eda_arr = _resample_to_1hz_mean(eda.to_numpy(), _EDA_HZ, n_seconds)
    temp_arr = _resample_to_1hz_mean(temp.to_numpy(), _TEMP_HZ, n_seconds)

    label_1hz = _label_mode_1hz(label_raw.to_numpy(), _LABEL_HZ, n_seconds)

    # Rolling 10-second mean for avg_bpm (NaN-aware)
    bpm_series = pd.Series(bpm_arr)
    avg_bpm_arr = bpm_series.rolling(10, min_periods=1).mean().to_numpy()

    bpm_valid = (~np.isnan(bpm_arr)) & (bpm_arr >= _BPM_VALID_LO) & (bpm_arr <= _BPM_VALID_HI)

    timestamp_ms = np.arange(n_seconds) * 1000

    df = pd.DataFrame({
        "timestamp_ms": timestamp_ms.astype(np.int64),
        "bpm": bpm_arr,
        "avg_bpm": avg_bpm_arr,
        "temp_c": temp_arr,
        "gsr": eda_arr,
        "label_code": label_1hz,
        "subject_id": subject_id,
        "bpm_valid": bpm_valid,
    })

    return df
