import math

import numpy as np
import pandas as pd
import pytest

from stress_detection.features.extractors import (
    extract_gsr_features,
    extract_hr_features,
    extract_temp_features,
)


def _make_window(n=30, **overrides) -> pd.DataFrame:
    """Synthetic 30-row window with sensible defaults."""
    data = {
        "bpm": [75.0] * n,
        "bpm_valid": [True] * n,
        "gsr": [100.0] * n,
        "temp_c": [36.5] * n,
    }
    data.update(overrides)
    return pd.DataFrame(data)


# ── HR features ───────────────────────────────────────────────────────────────

def test_hr_constant_bpm():
    w = _make_window(bpm=[75.0] * 30)
    f = extract_hr_features(w)
    assert f["hr_mean"] == pytest.approx(75.0)
    assert f["hr_std"] == pytest.approx(0.0, abs=1e-9)
    assert f["hr_min"] == pytest.approx(75.0)
    assert f["hr_max"] == pytest.approx(75.0)
    assert f["hr_range"] == pytest.approx(0.0)
    assert f["hr_slope"] == pytest.approx(0.0, abs=1e-9)
    assert f["hr_pnn_proxy"] == pytest.approx(0.0)


def test_hr_linear_increasing_slope():
    bpm = list(range(60, 90))  # 30 values, linearly increasing
    w = _make_window(bpm=bpm)
    f = extract_hr_features(w)
    assert f["hr_slope"] > 0


def test_hr_all_invalid_returns_nan():
    w = _make_window(bpm_valid=[False] * 30)
    f = extract_hr_features(w)
    for key in f:
        assert math.isnan(f[key]), f"{key} should be NaN"


def test_hr_fewer_than_5_valid_returns_nan():
    valid_flags = [False] * 26 + [True] * 4  # only 4 valid
    w = _make_window(bpm_valid=valid_flags)
    f = extract_hr_features(w)
    for key in f:
        assert math.isnan(f[key]), f"{key} should be NaN"


def test_hr_pnn_proxy():
    # Alternating 70 / 80 → every diff is 10 > 5
    bpm = [70.0, 80.0] * 15
    w = _make_window(bpm=bpm)
    f = extract_hr_features(w)
    assert f["hr_pnn_proxy"] == pytest.approx(1.0)


# ── GSR features ──────────────────────────────────────────────────────────────

def test_gsr_constant():
    w = _make_window(gsr=[100.0] * 30)
    f = extract_gsr_features(w)
    assert f["gsr_mean"] == pytest.approx(100.0)
    assert f["gsr_std"] == pytest.approx(0.0, abs=1e-9)
    assert f["gsr_range"] == pytest.approx(0.0)
    assert f["gsr_slope"] == pytest.approx(0.0, abs=1e-9)
    assert f["gsr_peaks"] == pytest.approx(0.0)


def test_gsr_peak_detection():
    # Flat baseline with one clear peak
    gsr = [100.0] * 10 + [115.0, 120.0, 115.0] + [100.0] * 17
    w = _make_window(gsr=gsr)
    f = extract_gsr_features(w)
    assert f["gsr_peaks"] >= 1.0


def test_gsr_peaks_unit_invariant():
    """gsr_peaks must fire on the same peak structure regardless of input units.

    Builds one peak pattern, then expresses it at two scales:
      - large ADC scale (~12-bit, values near 100), matching project hardware
      - small µS scale (values near 1), matching WESAD EDA
    Both must report the same non-zero peak count after z-score normalisation.
    """
    # Three clear peaks on a flat baseline (z-score space is what matters).
    pattern = (
        [0.0] * 5 + [1.0, 2.0, 1.0]
        + [0.0] * 5 + [1.0, 2.0, 1.0]
        + [0.0] * 5 + [1.0, 2.0, 1.0]
        + [0.0] * 6
    )
    assert len(pattern) == 30

    adc = [100.0 + 10.0 * v for v in pattern]   # large ADC-scale values
    micro = [1.0 + 0.1 * v for v in pattern]    # small µS-scale values

    peaks_adc = extract_gsr_features(_make_window(gsr=adc))["gsr_peaks"]
    peaks_micro = extract_gsr_features(_make_window(gsr=micro))["gsr_peaks"]

    assert peaks_adc > 0
    assert peaks_micro > 0
    assert peaks_adc == peaks_micro == 3.0


def test_gsr_rising_ramp_no_peaks():
    # Monotonically increasing - no local maxima, so find_peaks returns nothing
    gsr = list(range(90, 120))
    w = _make_window(gsr=gsr)
    f = extract_gsr_features(w)
    assert f["gsr_peaks"] == 0.0


def test_gsr_auc_positive():
    w = _make_window(gsr=[100.0] * 30)
    f = extract_gsr_features(w)
    assert f["gsr_auc"] > 0


def test_gsr_slope_linear():
    gsr = list(range(90, 120))
    w = _make_window(gsr=gsr)
    f = extract_gsr_features(w)
    assert f["gsr_slope"] == pytest.approx(1.0, rel=1e-5)


# ── Temp features ─────────────────────────────────────────────────────────────

def test_temp_constant():
    w = _make_window(temp_c=[36.5] * 30)
    f = extract_temp_features(w)
    assert f["temp_mean"] == pytest.approx(36.5)
    assert f["temp_std"] == pytest.approx(0.0, abs=1e-9)
    assert f["temp_slope"] == pytest.approx(0.0, abs=1e-9)
