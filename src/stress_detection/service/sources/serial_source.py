"""Serial input source - reads the ESP32 firmware's line protocol over USB.

Each sample is one newline-terminated comma-separated line in this order:

    timestamp,bpm,avg_bpm,gsr,temp_c

These fields come only from MAX30105 (heart rate), the GSR sensor (skin
conductance), and MLX90614 (temperature). See docs/hardware_serial_format.md.

Robustness (per the 4.2 brief):
  * Malformed / partial / header lines are logged and skipped - never crash.
  * If the USB port disappears mid-stream (device unplugged), the reader closes
    the handle and retries opening it with a bounded backoff, then resumes.

Stream timing: like CsvReplaySource, timestamp_ms is a fixed 1000 ms per sample
(sample_index * 1000), NOT the firmware's own timestamp. This keeps the
FeatureStreamer's count-based 30 s window / 5 s stride identical to the Phase 1
training pipeline regardless of serial jitter or a dropped sample.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from ..config import SerialConfig
from .base import SensorSample, SensorSource, valid_bpm

logger = logging.getLogger(__name__)

# Canonical live-wire field order (the recorded-CSV header minus `label`).
_FIELDS = ["timestamp", "bpm", "avg_bpm", "gsr", "temp_c"]
_MIN_FIELDS = len(_FIELDS)

_SAMPLE_PERIOD_MS = 1000  # 1 Hz data - fixed stream clock (see module docstring)
_RECONNECT_BACKOFF_S = 2.0
_MAX_RECONNECT_ATTEMPTS = 5


class SerialSource(SensorSource):
    def __init__(self, cfg: SerialConfig):
        self._port = cfg.port
        self._baudrate = cfg.baudrate
        self._serial = None
        self._running = False
        self._sample_idx = 0

    def _open(self):
        """Open the serial port. Returns the handle or None (logged on failure)."""
        try:
            import serial  # pyserial - lazy import so its absence doesn't break import
            handle = serial.Serial(self._port, self._baudrate, timeout=1)
            logger.info("SerialSource opened %s @ %d", self._port, self._baudrate)
            return handle
        except Exception as exc:  # noqa: BLE001 - log and stay down, never crash
            logger.warning("SerialSource could not open %s: %s", self._port, exc)
            return None

    async def start(self) -> None:
        self._serial = await asyncio.to_thread(self._open)
        self._running = self._serial is not None

    async def stop(self) -> None:
        self._running = False
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("SerialSource close failed: %s", exc)
            self._serial = None

    @staticmethod
    def _to_float(value: str, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _parse_line(self, line: str) -> SensorSample | None:
        """Parse one CSV line into a SensorSample, or None to skip it."""
        line = line.strip()
        if not line:
            return None
        # Tolerate an optional leading tag (e.g. "DATA," or "CSV,") some firmwares
        # prefix; strip it if the first token isn't numeric.
        parts = line.split(",")
        # Skip a header row if present (checked before any tag-stripping so the
        # "timestamp" header column isn't mistaken for a leading tag).
        if parts and parts[0].strip().lower() == "timestamp":
            return None
        # Tolerate an optional leading tag (e.g. "DATA," or "CSV,") some firmwares
        # prefix; strip it if the first token isn't numeric.
        if parts and not _looks_numeric(parts[0]):
            parts = parts[1:]
        if len(parts) < _MIN_FIELDS:
            logger.warning("SerialSource: short/malformed line skipped: %r", line)
            return None

        f = self._to_float
        bpm = valid_bpm(parts[1])
        avg_bpm = valid_bpm(parts[2])
        gsr = f(parts[3])
        temp_c = f(parts[4])

        ts_ms = self._sample_idx * _SAMPLE_PERIOD_MS
        self._sample_idx += 1
        return SensorSample(
            timestamp_ms=ts_ms,
            bpm=bpm, avg_bpm=avg_bpm, temp_c=temp_c, gsr=gsr,
            source_label=None,
        )

    async def _readline(self) -> bytes | None:
        """Read one line off the port. Returns None on a read error (triggers
        a reconnect attempt by the caller)."""
        try:
            return await asyncio.to_thread(self._serial.readline)
        except Exception as exc:  # noqa: BLE001 - e.g. SerialException on unplug
            logger.warning("SerialSource read failed (port lost?): %s", exc)
            return None

    async def _reconnect(self) -> bool:
        """Try to reopen the port with bounded backoff. Returns True on success."""
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:  # noqa: BLE001
                pass
            self._serial = None
        for attempt in range(1, _MAX_RECONNECT_ATTEMPTS + 1):
            if not self._running:
                return False
            logger.info("SerialSource reconnect attempt %d/%d to %s",
                        attempt, _MAX_RECONNECT_ATTEMPTS, self._port)
            self._serial = await asyncio.to_thread(self._open)
            if self._serial is not None:
                return True
            await asyncio.sleep(_RECONNECT_BACKOFF_S)
        return False

    async def stream(self) -> AsyncIterator[SensorSample]:
        if self._serial is None:
            await self.start()
        if self._serial is None:
            logger.warning("SerialSource: no open port, stream is empty")
            return
        while self._running:
            raw = await self._readline()
            if raw is None:
                # Read error - the device may have been unplugged. Try to recover.
                if not await self._reconnect():
                    logger.warning("SerialSource: reconnect exhausted, ending stream")
                    return
                continue
            if not raw:
                continue  # idle timeout, no data this tick
            line = raw.decode("utf-8", errors="replace")
            sample = self._parse_line(line)
            if sample is not None:
                yield sample


def _looks_numeric(token: str) -> bool:
    try:
        float(token.strip())
        return True
    except (TypeError, ValueError):
        return False
