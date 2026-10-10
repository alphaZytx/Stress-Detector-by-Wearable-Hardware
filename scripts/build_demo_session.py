"""Generate data/demo/canned_session.json - a curated 3-minute demo session.

Structure: baseline (0-60s) → stress (60-135s) → breathing recovery (135-165s,
smooth decay back toward baseline) → baseline (165-180s).

The samples come from the real project CSVs (baseline + stress), with the
recovery segment interpolated from stress values back to baseline values. Every
sample is run through the SAME FeatureStreamer + InferenceEngine the live service
uses, so the canned predictions are genuine model outputs, not faked.

The stress block is 75 s and drawn from a CLEAN high-stress region of the source
CSV (rows ~150-290, avoiding the two ambiguous windows around rows 74 and 143).
This is deliberate: the EMA needs ~20 s to climb past the 0.7 alert threshold,
so a continuous, dip-free stress plateau is required for the smoothed P(stress)
to stay ≥0.7 for the >30 s the breathing auto-trigger banner needs. With this
layout the banner fires ~t=130 s.

Usage:
    python3 scripts/build_demo_session.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stress_detection.service.config import get_service_config  # noqa: E402
from stress_detection.service.features.streamer import FeatureStreamer  # noqa: E402
from stress_detection.service.inference.engine import InferenceEngine  # noqa: E402
from stress_detection.service.sources.base import SensorSample, valid_bpm  # noqa: E402

_DURATION_S = 180
_OUT_PATH = _REPO_ROOT / "data" / "demo" / "canned_session.json"

_EVENTS = [
    {"t_s": 0, "phase": "baseline", "narration": "Resting state."},
    {"t_s": 60, "phase": "stress", "narration": "Cognitive stress task begins."},
    {"t_s": 135, "phase": "breathing", "narration": "Breathing exercise - recovery."},
    {"t_s": 165, "phase": "baseline", "narration": "Returned to baseline."},
]

# Sensor fields carried per sample (everything SensorSample needs).
_NUMERIC = [
    "bpm", "avg_bpm", "temp_c", "gsr",
]


def _load(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _row_to_sample(row: pd.Series, ts_ms: int, phase: str) -> SensorSample:
    def f(col: str, default: float = 0.0) -> float:
        v = row.get(col, default)
        return float(v) if pd.notna(v) else default

    return SensorSample(
        timestamp_ms=ts_ms,
        bpm=valid_bpm(row.get("bpm")),
        avg_bpm=valid_bpm(row.get("avg_bpm")),
        temp_c=f("temp_c"),
        gsr=f("gsr"),
        source_label=phase,
    )


def _build_sample_rows() -> list[tuple[pd.Series, str]]:
    """Return 180 (row, phase) pairs: baseline(60) → stress(75) → recovery(30) →
    baseline(15). The stress block + recovery anchor come from a CONTIGUOUS clean
    high-stress slice so the smoothed P(stress) plateau is unbroken."""
    baseline = _load(_REPO_ROOT / "data/raw/revised_sensors_baseline__1_.csv")
    stress = _load(_REPO_ROOT / "data/raw/revised_sensors_stress__1_.csv")

    # Baseline: skip sensor warmup. Stress: use the clean region (rows ~150+),
    # which avoids the two ambiguous stress windows (around rows 74 and 143).
    base_slice = baseline.iloc[30:150].reset_index(drop=True)    # 120 baseline rows
    stress_clean = stress.iloc[150:290].reset_index(drop=True)   # ~140 clean stress rows

    rows: list[tuple[pd.Series, str]] = []

    # 0-60s baseline
    for i in range(60):
        rows.append((base_slice.iloc[i], "baseline"))

    # 60-135s stress (75 s of dip-free stress so the EMA can sustain ≥0.7 >30s)
    for i in range(75):
        rows.append((stress_clean.iloc[i], "stress"))

    # 135-165s breathing recovery: linear blend stress→baseline over 30s,
    # continuing contiguously from the stress block (stress_clean[75:105]).
    stress_anchor = stress_clean.iloc[75:105].reset_index(drop=True)
    base_anchor = base_slice.iloc[60:90].reset_index(drop=True)
    for i in range(30):
        w = (i + 1) / 30.0  # 0→1, fully baseline by the end
        blended = stress_anchor.iloc[i].copy()
        for col in _NUMERIC:
            if col in blended and col in base_anchor.columns:
                s_val = stress_anchor.iloc[i].get(col)
                b_val = base_anchor.iloc[i].get(col)
                if pd.notna(s_val) and pd.notna(b_val):
                    blended[col] = (1 - w) * float(s_val) + w * float(b_val)
        rows.append((blended, "breathing"))

    # 165-180s baseline
    for i in range(15):
        rows.append((base_slice.iloc[90 + i], "baseline"))

    assert len(rows) == _DURATION_S, len(rows)
    return rows


def main() -> None:
    cfg = get_service_config()
    streamer = FeatureStreamer(cfg.window_s, cfg.stride_s, cfg.sampling_hz)
    # Same resolution the service uses, so the canned session is produced by
    # whatever the deployment actually serves - falling back to the SVM
    # baseline when the ensemble artifacts have not been generated yet.
    engine = InferenceEngine(
        cfg.inference.model_path,
        smoothing_method=cfg.inference.smoothing.method,
        smoothing_window=cfg.inference.smoothing.window,
        ema_alpha=cfg.inference.smoothing.ema_alpha,
        model_type=cfg.inference.model_type,
        fallback_model_path=cfg.inference.fallback_model_path,
    )

    rows = _build_sample_rows()
    samples: list[dict] = []
    predictions: list[dict] = []
    features: list[dict] = []

    for i, (row, phase) in enumerate(rows):
        ts_ms = i * 1000
        sample = _row_to_sample(row, ts_ms, phase)
        samples.append(sample.to_dict())

        feats = streamer.push(sample)
        if feats is not None:
            pred = engine.predict(feats, ts_ms)
            predictions.append(pred.model_dump())
            # Carry features (with their timestamp) so demo mode can populate the
            # HRV panel and feature-derived widgets exactly like the live stream.
            features.append({**feats, "timestamp_ms": ts_ms})

    payload = {
        "session_id": "DEMO",
        "duration_s": _DURATION_S,
        "events": _EVENTS,
        "samples": samples,
        "features": features,
        "predictions": predictions,
    }

    _OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUT_PATH.write_text(json.dumps(payload, indent=2))

    n_stress = sum(1 for p in predictions if p["smoothed_label"] == "stress")
    print(f"Wrote {_OUT_PATH}")
    print(f"  samples={len(samples)} predictions={len(predictions)}")
    print(f"  smoothed-stress predictions: {n_stress}/{len(predictions)}")


if __name__ == "__main__":
    main()
