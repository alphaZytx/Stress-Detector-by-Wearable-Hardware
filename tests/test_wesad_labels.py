"""Tests for WESAD label mapping functions."""

import numpy as np
import pytest

from stress_detection.io.wesad_labels import map_to_binary, map_to_three_class


RAW = np.array([0, 1, 2, 3, 4, 5])


def _nan_equal(a, b):
    """Compare arrays treating NaN == NaN."""
    return (np.isnan(a) == np.isnan(b)).all() and np.allclose(
        a[~np.isnan(a)], b[~np.isnan(b)]
    )


def test_binary_mapping():
    result = map_to_binary(RAW)
    expected = np.array([np.nan, 0.0, 1.0, np.nan, np.nan, np.nan])
    assert _nan_equal(result, expected), f"Got {result}"


def test_three_class_mapping():
    result = map_to_three_class(RAW)
    expected = np.array([np.nan, 0.0, 2.0, 1.0, 0.0, np.nan])
    assert _nan_equal(result, expected), f"Got {result}"


def test_binary_mapping_all_nan_for_unknown():
    result = map_to_binary(np.array([0, 3, 4, 5, 6, 7]))
    assert np.all(np.isnan(result))


def test_binary_returns_float_array():
    result = map_to_binary(RAW)
    assert result.dtype == float


def test_three_class_returns_float_array():
    result = map_to_three_class(RAW)
    assert result.dtype == float
