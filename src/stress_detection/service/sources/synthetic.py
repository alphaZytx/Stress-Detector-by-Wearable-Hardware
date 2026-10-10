"""Synthetic wearable source for running the full stack without hardware.

The generator emits the same :class:`SensorSample` objects as the ESP32 source
at a logical rate of 1 Hz.  Values are stochastic but physiologically shaped:
they drift smoothly, contain small sensor noise, and cycle through baseline,
stress, and recovery phases.  The samples still travel through the normal
FeatureStreamer and trained SVM; no prediction is fabricated here.

``speed`` changes wall-clock playback only.  Stream timestamps always advance
by 1000 ms so the model continues to receive the 30-s windows it was trained on.
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
from typing import AsyncIterator

from ..config import SyntheticConfig
from .base import SensorSample, SensorSource, valid_bpm

logger = logging.getLogger(__name__)

_SAMPLE_PERIOD_MS = 1000


class SyntheticSource(SensorSource):
    """Generate an endless baseline → stress → recovery wearable stream."""

    def __init__(self, cfg: SyntheticConfig):
        self._speed = max(float(cfg.speed), 1e-9)
        self._seed = int(cfg.seed)
        self._phase_lengths = {
            "baseline": max(int(cfg.baseline_s), 1),
            "stress": max(int(cfg.stress_s), 1),
            "recovery": max(int(cfg.recovery_s), 1),
        }
        self._rng = random.Random(self._seed)
        self._running = False
        self._sample_idx = 0
        self._bpm = 72.0
        self._avg_bpm = 72.0
        self._gsr = 67.0
        self._temp_c = 34.2
        self._gsr_response = 0.0

    async def start(self) -> None:
        self._running = True
        logger.info(
            "SyntheticSource ready: seed=%d speed=%.1f phases=%s",
            self._seed,
            self._speed,
            self._phase_lengths,
        )

    async def stop(self) -> None:
        self._running = False

    def _phase(self, sample_idx: int) -> str:
        cycle_s = sum(self._phase_lengths.values())
        offset = sample_idx % cycle_s
        for phase in ("baseline", "stress", "recovery"):
            length = self._phase_lengths[phase]
            if offset < length:
                return phase
            offset -= length
        return "recovery"  # defensive; the loop above always returns

    def _approach(self, value: float, target: float, rate: float, noise: float) -> float:
        return value + rate * (target - value) + self._rng.gauss(0.0, noise)

    def _make_sample(self) -> SensorSample:
        idx = self._sample_idx
        phase = self._phase(idx)

        # Targets mirror the rough scale of the project's own ESP32 recordings.
        # Recovery intentionally sits between stress and baseline so transitions
        # look like a real signal rather than a hard step in the dashboard.
        if phase == "stress":
            bpm_target, bpm_noise = 77.0, 14.0
            gsr_target, gsr_noise, temp_target, temp_noise = 121.0, 9.0, 34.44, 0.025
            response_probability, response_amplitude = 0.12, (8.0, 22.0)
        elif phase == "recovery":
            bpm_target, bpm_noise = 75.0, 10.0
            gsr_target, gsr_noise, temp_target, temp_noise = 78.0, 8.0, 34.28, 0.025
            response_probability, response_amplitude = 0.04, (3.0, 10.0)
        else:
            bpm_target, bpm_noise = 74.0, 9.0
            gsr_target, gsr_noise, temp_target, temp_noise = 66.0, 8.0, 34.23, 0.020
            response_probability, response_amplitude = 0.02, (2.0, 6.0)

        # Smooth random walks plus periodic components approximate sensor drift,
        # breathing-related HR modulation, and transient GSR responses.
        respiratory_wave = math.sin(idx * 2.0 * math.pi / 10.0)
        self._bpm = self._approach(
            self._bpm, bpm_target + 2.0 * respiratory_wave, 0.12, 0.4
        )
        measured_bpm = min(
            max(self._bpm + self._rng.gauss(0.0, bpm_noise), 45.0), 180.0
        )
        self._avg_bpm = self._approach(self._avg_bpm, measured_bpm, 0.12, 0.15)

        self._gsr_response *= 0.82
        if self._rng.random() < response_probability:
            self._gsr_response += self._rng.uniform(*response_amplitude)
        self._gsr = self._approach(
            self._gsr, gsr_target + self._gsr_response, 0.14, 0.6
        )
        measured_gsr = max(self._gsr + self._rng.gauss(0.0, gsr_noise), 1.0)
        self._temp_c = self._approach(self._temp_c, temp_target, 0.08, 0.003)
        measured_temp = min(
            max(self._temp_c + self._rng.gauss(0.0, temp_noise), 30.0), 40.0
        )

        # Rare PPG dropout exercises the real validity gate while keeping every
        # 30-s window comfortably above the required 70% valid samples.
        reported_bpm = None if self._rng.random() < 0.015 else valid_bpm(measured_bpm)

        sample = SensorSample(
            timestamp_ms=idx * _SAMPLE_PERIOD_MS,
            bpm=reported_bpm,
            avg_bpm=valid_bpm(self._avg_bpm),
            temp_c=measured_temp,
            gsr=measured_gsr,
            source_label=phase,
        )
        self._sample_idx += 1
        return sample

    async def stream(self) -> AsyncIterator[SensorSample]:
        if not self._running:
            await self.start()

        sleep_s = 1.0 / self._speed
        first = True
        while self._running:
            if not first:
                await asyncio.sleep(sleep_s)
            first = False
            yield self._make_sample()
