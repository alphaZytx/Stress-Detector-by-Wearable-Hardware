"""Sanity check: does a model separate the project baseline/stress CSVs?

Reproduces the LIVE pipeline offline (CsvReplaySource row parsing →
FeatureStreamer 30s/5s → InferenceEngine EMA) over each project CSV and reports
the predicted-stress proportion (raw per-window and EMA-smoothed) for each model.

This is the Phase 2 §2.4 "critical finding" sanity check, re-run at Phase 4.1
against the v2 models. It also optionally applies per-user calibration offsets
(resting baselines computed from the baseline CSV) to test whether calibration
lets the WESAD-only model transfer to the project's raw-ADC hardware.

Usage:
  python3 scripts/check_model_transfer.py
  python3 scripts/check_model_transfer.py --version v2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stress_detection.config import get_config  # noqa: E402
from stress_detection.service.features.streamer import FeatureStreamer  # noqa: E402
from stress_detection.service.inference.engine import (  # noqa: E402
    CalibrationOffsets,
    InferenceEngine,
)
from stress_detection.service.sources.base import SensorSample, valid_bpm  # noqa: E402

_WINDOW_S = 30
_STRIDE_S = 5
_SAMPLE_PERIOD_MS = 1000


def _rows_to_samples(csv_path: Path) -> list[SensorSample]:
    df = pd.read_csv(csv_path)

    def _f(row: pd.Series, col: str, default: float = 0.0) -> float:
        val = row.get(col, default)
        return float(val) if pd.notna(val) else default

    samples: list[SensorSample] = []
    ts = 0
    for _, row in df.iterrows():
        label = row.get("label")
        samples.append(
            SensorSample(
                timestamp_ms=ts,
                bpm=valid_bpm(row.get("bpm")),
                avg_bpm=valid_bpm(row.get("avg_bpm")),
                temp_c=_f(row, "temp_c"),
                gsr=_f(row, "gsr"),
                source_label=str(label) if pd.notna(label) else None,
            )
        )
        ts += _SAMPLE_PERIOD_MS
    return samples


def _resting_baselines(csv_path: Path) -> CalibrationOffsets:
    """Per-user resting baselines (means over the baseline CSV)."""
    df = pd.read_csv(csv_path)
    bpm = pd.to_numeric(df.get("bpm"), errors="coerce")
    bpm = bpm[(bpm >= 40) & (bpm <= 200)]
    return CalibrationOffsets(
        hr_baseline=float(bpm.mean()) if len(bpm) else None,
        gsr_baseline=float(pd.to_numeric(df["gsr"], errors="coerce").mean()),
        temp_baseline=float(pd.to_numeric(df["temp_c"], errors="coerce").mean()),
    )


def _run(model_path: Path, samples: list[SensorSample],
         calibration: CalibrationOffsets | None = None) -> tuple[float, float, int]:
    engine = InferenceEngine(model_path, smoothing_method="ema",
                             smoothing_window=6, ema_alpha=0.3)
    streamer = FeatureStreamer(window_s=_WINDOW_S, stride_s=_STRIDE_S)
    raw_stress = 0
    ema_stress = 0
    n = 0
    for s in samples:
        feats = streamer.push(s)
        if feats is None:
            continue
        pred = engine.predict(feats, timestamp_ms=s.timestamp_ms, calibration=calibration)
        n += 1
        raw_stress += int(pred.label == "stress")
        ema_stress += int(pred.smoothed_label == "stress")
    if n == 0:
        return 0.0, 0.0, 0
    return raw_stress / n, ema_stress / n, n


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v2")
    args = parser.parse_args()
    ver = args.version

    cfg = get_config()
    raw = cfg.paths.data_raw
    baseline_csv = raw / "revised_sensors_baseline__1_.csv"
    stress_csv = raw / "revised_sensors_stress__1_.csv"

    base_samples = _rows_to_samples(baseline_csv)
    stress_samples = _rows_to_samples(stress_csv)

    wesad = cfg.paths.data_models / f"svm_wesad_{ver}.joblib"
    combined = cfg.paths.data_models / f"svm_combined_{ver}.joblib"

    cal = _resting_baselines(baseline_csv)

    print(f"\n=== Model transfer sanity check ({ver}) ===")
    print(f"Resting baselines from baseline CSV: "
          f"hr={cal.hr_baseline:.1f} gsr={cal.gsr_baseline:.1f} temp={cal.temp_baseline:.2f}")
    print(f"{'model / condition':<34}{'raw %stress':>13}{'ema %stress':>13}{'emits':>8}")
    print("-" * 68)

    for name, mp in [("WESAD-only", wesad), ("Combined", combined)]:
        for cond, samples in [("baseline", base_samples), ("stress", stress_samples)]:
            r, e, n = _run(mp, samples)
            print(f"{name + ' / ' + cond:<34}{r*100:>12.0f}%{e*100:>12.0f}%{n:>8}")

    print("\n--- WESAD-only WITH per-user calibration (deviation-from-baseline) ---")
    for cond, samples in [("baseline", base_samples), ("stress", stress_samples)]:
        r, e, n = _run(wesad, samples, calibration=cal)
        print(f"{'WESAD-only+cal / ' + cond:<34}{r*100:>12.0f}%{e*100:>12.0f}%{n:>8}")


if __name__ == "__main__":
    main()
