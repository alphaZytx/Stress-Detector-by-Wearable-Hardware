"""Calibration-affects-inference tests (3.0.b).

Covers the unit-level offset math on InferenceEngine and the session-level
wiring: posting calibration → starting a session → the engine applying it.
"""

from __future__ import annotations

import asyncio

import pandas as pd
import pytest

from stress_detection.config import get_config
from stress_detection.service.config import get_service_config
from stress_detection.service.inference.loader import resolve_model_path
from stress_detection.service.features.schema import FEATURE_COLUMNS
from stress_detection.service.inference.engine import (
    CalibrationOffsets,
    InferenceEngine,
)
from stress_detection.service.runtime import Runtime
from stress_detection.service.sessions.manager import SessionManager


@pytest.fixture(scope="module")
def feature_dict():
    cfg = get_service_config()
    parquet = get_config().paths.data_features / "features_wesad_v1.parquet"
    row = pd.read_parquet(parquet).iloc[0]
    return {c: float(row[c]) for c in FEATURE_COLUMNS}


@pytest.fixture
def model_path():
    """Whatever the service is configured to serve, resolved the same way the
    app resolves it - glob expanded, falling back to the SVM baseline when the
    ensemble artifacts have not been generated yet."""
    cfg = get_service_config()
    path, _ = resolve_model_path(
        cfg.inference.model_path, cfg.inference.fallback_model_path
    )
    return path


def test_no_calibration_flag_false(model_path, feature_dict):
    engine = InferenceEngine(model_path)
    pred = engine.predict(feature_dict)
    assert pred.calibration_applied is False


def test_empty_calibration_is_passthrough(model_path, feature_dict):
    engine = InferenceEngine(model_path)
    pred = engine.predict(feature_dict, calibration=CalibrationOffsets())
    assert pred.calibration_applied is False


def test_calibration_shifts_features(model_path, feature_dict):
    """predict(features, calibration=offsets) must equal predict(manually-offset)."""
    offsets = CalibrationOffsets(hr_baseline=10.0, gsr_baseline=5.0, temp_baseline=1.0)

    # Manually offset the exact feature groups the engine targets.
    manual = dict(feature_dict)
    for k in ("hr_mean", "hr_min", "hr_max"):
        manual[k] -= 10.0
    for k in ("gsr_mean", "gsr_min", "gsr_max"):
        manual[k] -= 5.0
    manual["temp_mean"] -= 1.0

    engine_a = InferenceEngine(model_path)
    via_calibration = engine_a.predict(feature_dict, calibration=offsets)

    engine_b = InferenceEngine(model_path)
    via_manual = engine_b.predict(manual)

    assert via_calibration.calibration_applied is True
    assert via_calibration.raw_proba["stress"] == pytest.approx(
        via_manual.raw_proba["stress"]
    )
    assert via_calibration.label == via_manual.label


def test_calibration_changes_the_prediction_proba(model_path, feature_dict):
    """A large baseline offset must actually move the model output, proving the
    offset reaches the model (not silently dropped)."""
    engine = InferenceEngine(model_path)
    base = engine.predict(feature_dict)

    engine2 = InferenceEngine(model_path)
    big = CalibrationOffsets(hr_baseline=40.0, gsr_baseline=60.0, temp_baseline=2.0)
    shifted = engine2.predict(feature_dict, calibration=big)

    assert shifted.calibration_applied is True
    assert shifted.raw_proba["stress"] != pytest.approx(base.raw_proba["stress"])


def test_runtime_loads_calibration_at_session_start(tmp_path, model_path):
    """Post calibration → start a session for that user → runtime holds offsets
    and the engine applies them; use_calibration=False disables it."""

    async def run():
        mgr = SessionManager(tmp_path / "s.sqlite", tmp_path / "exp")
        await mgr.initialize()
        await mgr.set_calibration(
            "user-cal",
            {"hr_baseline": 12.0, "gsr_baseline": 7.0, "temp_baseline": 0.5},
        )
        engine = InferenceEngine(model_path)
        runtime = Runtime(get_service_config(), None, None, engine, None, mgr)

        # Opted-in session for the calibrated user → calibration loaded.
        await runtime.start_session("lbl", None, "user-cal", use_calibration=True)
        on = runtime._calibration
        await runtime.stop_session()
        off_after_stop = runtime._calibration

        # Opted-out session → no calibration even though it exists.
        await runtime.start_session("lbl", None, "user-cal", use_calibration=False)
        opted_out = runtime._calibration
        await runtime.stop_session()

        # User with no calibration → none loaded.
        await runtime.start_session("lbl", None, "user-none", use_calibration=True)
        none_user = runtime._calibration
        await runtime.stop_session()

        return on, off_after_stop, opted_out, none_user

    on, off_after_stop, opted_out, none_user = asyncio.run(run())
    assert on is not None and on.hr_baseline == 12.0 and on.gsr_baseline == 7.0
    assert off_after_stop is None
    assert opted_out is None
    assert none_user is None


def test_runtime_resets_engine_smoothing_at_session_start(tmp_path, model_path, feature_dict):
    """Regression test: the one long-lived InferenceEngine is shared across
    every session's lifetime. Without an explicit reset, a new session's first
    predictions would be smoothed using EMA/majority-vote state left behind by
    whatever ran immediately before it (a previous session, or the idle
    pre-session stream) - showing a stale label right after clicking Start."""

    async def run():
        mgr = SessionManager(tmp_path / "s2.sqlite", tmp_path / "exp2")
        await mgr.initialize()
        engine = InferenceEngine(model_path, smoothing_method="ema", ema_alpha=0.3)
        runtime = Runtime(get_service_config(), None, None, engine, None, mgr)

        # Drive the engine hard toward "stress" before any session starts -
        # simulating leftover state from a prior session or idle streaming.
        stressed = dict(feature_dict)
        for _ in range(20):
            engine.predict(stressed, calibration=None)
        ema_before_session = engine._ema

        await runtime.start_session("lbl", None, None, use_calibration=False)
        ema_after_start = engine._ema
        labels_after_start = list(engine._labels)
        await runtime.stop_session()

        return ema_before_session, ema_after_start, labels_after_start

    ema_before, ema_after, labels_after = asyncio.run(run())
    assert ema_before is not None
    assert ema_after is None, "EMA state leaked from before session start into the new session"
    assert labels_after == []
