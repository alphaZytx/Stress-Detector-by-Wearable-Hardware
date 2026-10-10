"""Streaming feature extractor - the live counterpart of build_feature_table().

Maintains a rolling buffer of recent SensorSamples sized to ``window_s`` seconds.
Every ``stride_s`` seconds of stream time it calls the EXISTING Phase 1
build_feature_table() on the current buffer and emits the resulting 18-feature
dict. Extractors are NOT reimplemented here - we reuse the offline pipeline so the
live features are byte-for-byte the ones the model was trained on.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from stress_detection.features.pipeline import build_feature_table

from ..sources.base import SensorSample
from .schema import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

# Columns the mini-DataFrame must carry for build_feature_table() to work.
_BUFFER_COLUMNS = [
    "timestamp_ms", "bpm", "bpm_valid", "gsr", "temp_c",
    "condition", "label",
]


class FeatureStreamer:
    """Rolling-window feature extractor over a live SensorSample stream."""

    def __init__(self, window_s: int, stride_s: int, sampling_hz: int = 1):
        self._window_s = window_s
        self._stride_ms = stride_s * 1000
        self._sampling_hz = sampling_hz
        self._window_rows = window_s * sampling_hz
        self._df = pd.DataFrame(columns=_BUFFER_COLUMNS)
        self._last_emit_ms: int | None = None

    @property
    def buffer_seconds(self) -> int:
        """Current buffer length in seconds, capped at window_s."""
        return int(min(self._window_s, len(self._df) / self._sampling_hz))

    def _append(self, sample: SensorSample) -> None:
        row = {
            "timestamp_ms": sample.timestamp_ms,
            "bpm": sample.bpm if sample.bpm is not None else np.nan,
            "bpm_valid": sample.bpm is not None,
            "gsr": sample.gsr,
            "temp_c": sample.temp_c if sample.temp_c is not None else np.nan,
            "condition": "live",
            "label": sample.source_label if sample.source_label is not None else "live",
        }
        new_row = pd.DataFrame([row], columns=_BUFFER_COLUMNS)
        # Avoid concat-with-empty (pandas FutureWarning) on the first sample.
        self._df = new_row if self._df.empty else pd.concat(
            [self._df, new_row], ignore_index=True
        )

    def _trim(self, latest_ms: int) -> None:
        # Keep only samples strictly newer than (latest - window_s*1000). At 1 Hz
        # this yields exactly window_rows samples aligned to the most recent data,
        # matching Phase 1's count-based windowing (window_s * sampling_hz rows).
        cutoff = latest_ms - self._window_s * 1000
        self._df = self._df[self._df["timestamp_ms"] > cutoff].reset_index(drop=True)

    def _compute(self) -> dict | None:
        feat_df = build_feature_table(self._df)
        if feat_df.empty:
            # build_feature_table drops windows failing the bpm_valid gate.
            return None
        # Use the most recent window row, keeping the canonical feature order.
        row = feat_df.iloc[-1]
        feats = {col: float(row[col]) for col in FEATURE_COLUMNS}
        return feats

    def push(self, sample: SensorSample) -> dict | None:
        """Add one sample; return an 18-feature dict at a stride boundary, else None."""
        self._append(sample)
        latest_ms = int(sample.timestamp_ms)
        self._trim(latest_ms)

        if len(self._df) < self._window_rows:
            return None  # buffer not yet full (< window_s of data)

        if self._last_emit_ms is not None and (latest_ms - self._last_emit_ms) < self._stride_ms:
            return None  # not yet at the next stride boundary

        feats = self._compute()
        if feats is None:
            return None  # window failed the validity gate - no emit, no crash

        self._last_emit_ms = latest_ms
        return feats
