"""Tests for WESAD loader using a synthetic pickle fixture (no real data needed)."""

import pickle
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from stress_detection.io.wesad import load_wesad_subject, build_wesad_1hz

# Synthetic recording length: 20 seconds of data
_SECS = 20
_BVP_HZ = 64
_EDA_HZ = 4
_TEMP_HZ = 4
_LABEL_HZ = 700


def _make_fake_wesad_dict(secs: int = _SECS) -> dict:
    """Create a minimal WESAD-shaped data dict for testing."""
    rng = np.random.default_rng(0)

    # BVP: simulate a pulsatile signal with peaks every ~0.8 s (~75 BPM)
    t = np.arange(secs * _BVP_HZ) / _BVP_HZ
    bvp = np.sin(2 * np.pi * 1.25 * t) + 0.1 * rng.standard_normal(len(t))

    return {
        "signal": {
            "wrist": {
                "BVP": bvp.reshape(-1, 1),
                "EDA": rng.uniform(1.0, 5.0, (secs * _EDA_HZ, 1)),
                "TEMP": (rng.uniform(33.0, 35.0, (secs * _TEMP_HZ, 1))),
            },
            "chest": {},
        },
        # Labels: alternating baseline (1) and stress (2) each second
        "label": np.tile([1, 2], secs * _LABEL_HZ // 2 + 1)[: secs * _LABEL_HZ],
        "subject": "S_test",
    }


@pytest.fixture
def fake_wesad_dir(tmp_path: Path) -> Path:
    """Write a fake WESAD pickle to a temp dir and return the root dir."""
    subject_id = "S99"
    subj_dir = tmp_path / subject_id
    subj_dir.mkdir()
    fake_data = _make_fake_wesad_dict()
    pkl_path = subj_dir / f"{subject_id}.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump(fake_data, f, protocol=2)
    return tmp_path


class TestLoadWesadSubject:
    def test_returns_expected_keys(self, fake_wesad_dir):
        result = load_wesad_subject("S99", data_dir=fake_wesad_dir)
        assert set(result.keys()) == {
            "subject_id", "wrist_bvp", "wrist_eda", "wrist_temp", "label"
        }

    def test_subject_id_matches(self, fake_wesad_dir):
        result = load_wesad_subject("S99", data_dir=fake_wesad_dir)
        assert result["subject_id"] == "S99"

    def test_wrist_bvp_is_series(self, fake_wesad_dir):
        result = load_wesad_subject("S99", data_dir=fake_wesad_dir)
        assert isinstance(result["wrist_bvp"], pd.Series)

    def test_label_is_series_of_ints(self, fake_wesad_dir):
        result = load_wesad_subject("S99", data_dir=fake_wesad_dir)
        assert isinstance(result["label"], pd.Series)
        assert result["label"].dtype in (np.int32, np.int64, int)

    def test_missing_subject_raises(self, fake_wesad_dir):
        with pytest.raises(FileNotFoundError):
            load_wesad_subject("S_MISSING", data_dir=fake_wesad_dir)


class TestBuildWesad1Hz:
    def test_output_has_required_columns(self, fake_wesad_dir):
        subj = load_wesad_subject("S99", data_dir=fake_wesad_dir)
        df = build_wesad_1hz(subj)
        required = {
            "timestamp_ms", "bpm", "avg_bpm", "temp_c", "gsr",
            "label_code", "subject_id", "bpm_valid",
        }
        assert required.issubset(set(df.columns)), \
            f"Missing: {required - set(df.columns)}"

    def test_subject_id_column(self, fake_wesad_dir):
        subj = load_wesad_subject("S99", data_dir=fake_wesad_dir)
        df = build_wesad_1hz(subj)
        assert (df["subject_id"] == "S99").all()

    def test_row_count_is_n_seconds(self, fake_wesad_dir):
        subj = load_wesad_subject("S99", data_dir=fake_wesad_dir)
        df = build_wesad_1hz(subj)
        assert len(df) == _SECS

    def test_bpm_valid_is_bool(self, fake_wesad_dir):
        subj = load_wesad_subject("S99", data_dir=fake_wesad_dir)
        df = build_wesad_1hz(subj)
        assert df["bpm_valid"].dtype == bool
