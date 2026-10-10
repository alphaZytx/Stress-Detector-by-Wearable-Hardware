"""CSV replay source - replays recorded sensor CSVs as if they were live.

This is the default source while the Raspberry Pi is not yet available.

Timing note (deviation from the literal prompt, documented intentionally):
  ``timestamp_ms`` increments by 1000 ms per sample (the 1 Hz data/stream
  period), independent of ``speed``. ``speed`` only controls the wall-clock
  sleep between emissions (1.0 / speed seconds). This is required so the
  downstream FeatureStreamer's window/stride math (30 s window = 30 samples,
  5 s stride) matches the Phase 1 training pipeline exactly, and so the 2.3
  exit gate holds (speed=10 → one emit per ~0.5 s wall = 5 s stream time).
  Treating timestamp_ms as wall-clock (1000/speed per sample) would silently
  rescale the windows and break feature parity with the trained model.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator

import pandas as pd

from ..config import CsvReplayConfig
from .base import SensorSample, SensorSource, valid_bpm

logger = logging.getLogger(__name__)

_SAMPLE_PERIOD_MS = 1000  # 1 Hz data


class CsvReplaySource(SensorSource):
    def __init__(self, cfg: CsvReplayConfig):
        self._files: list[Path] = list(cfg.files)
        self._loop = cfg.loop
        self._speed = max(cfg.speed, 1e-9)
        self._df: pd.DataFrame | None = None
        self._running = False

    async def start(self) -> None:
        frames = []
        for path in self._files:
            df = pd.read_csv(path)
            df = df.rename(columns={"timestamp": "orig_timestamp_ms"})
            frames.append(df)
        if not frames:
            raise ValueError("CsvReplaySource: no files configured")
        self._df = pd.concat(frames, ignore_index=True)
        self._running = True
        logger.info(
            "CsvReplaySource ready: %d rows from %d file(s), speed=%.1f loop=%s",
            len(self._df), len(self._files), self._speed, self._loop,
        )

    async def stop(self) -> None:
        self._running = False

    def _row_to_sample(self, row: pd.Series, ts_ms: int) -> SensorSample:
        def _f(col: str, default: float = 0.0) -> float:
            val = row.get(col, default)
            return float(val) if pd.notna(val) else default

        label = row.get("label")
        return SensorSample(
            timestamp_ms=ts_ms,
            bpm=valid_bpm(row.get("bpm")),
            avg_bpm=valid_bpm(row.get("avg_bpm")),
            temp_c=_f("temp_c"),
            gsr=_f("gsr"),
            source_label=str(label) if pd.notna(label) else None,
        )

    async def stream(self) -> AsyncIterator[SensorSample]:
        if self._df is None:
            await self.start()
        assert self._df is not None

        sleep_s = 1.0 / self._speed
        ts_ms = 0
        first = True
        while self._running:
            for _, row in self._df.iterrows():
                if not self._running:
                    return
                if not first:
                    await asyncio.sleep(sleep_s)
                first = False
                yield self._row_to_sample(row, ts_ms)
                ts_ms += _SAMPLE_PERIOD_MS
            if not self._loop:
                return
