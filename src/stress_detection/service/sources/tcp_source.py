"""TCP input source - line-delimited JSON, one sample object per line.

This is the protocol the future Raspberry Pi will use: the Pi reads its sensors,
builds one JSON object per 1 Hz sample with the SensorSample field names as keys,
and sends each as a newline-terminated line over a TCP socket.

Example payload (one line):
    {"timestamp_ms":1234,"bpm":72,"avg_bpm":71,"gsr":68,"temp_c":34.2}

Unknown keys are ignored; missing optional keys fall back to defaults. The
payload's own timestamp_ms is used (the Pi owns stream time on this transport).
A line that fails to parse logs a warning and is skipped.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from ..config import TcpConfig
from .base import SensorSample, SensorSource, valid_bpm

logger = logging.getLogger(__name__)


class TcpSource(SensorSource):
    def __init__(self, cfg: TcpConfig):
        self._host = cfg.host
        self._port = cfg.port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._running = False

    async def start(self) -> None:
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self._host, self._port
            )
            self._running = True
            logger.info("TcpSource connected to %s:%d", self._host, self._port)
        except OSError as exc:
            logger.warning("TcpSource could not connect to %s:%d: %s",
                           self._host, self._port, exc)
            self._reader = None
            self._writer = None
            self._running = False

    async def stop(self) -> None:
        self._running = False
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except OSError as exc:
                logger.warning("TcpSource close failed: %s", exc)
            self._writer = None
            self._reader = None

    @staticmethod
    def _parse_payload(payload: dict) -> SensorSample:
        def _f(key: str, default: float = 0.0) -> float:
            val = payload.get(key, default)
            return float(val) if val is not None else default

        return SensorSample(
            timestamp_ms=int(payload.get("timestamp_ms", 0)),
            bpm=valid_bpm(payload.get("bpm")),
            avg_bpm=valid_bpm(payload.get("avg_bpm")),
            temp_c=_f("temp_c"),
            gsr=_f("gsr"),
            source_label=payload.get("source_label"),
        )

    async def stream(self) -> AsyncIterator[SensorSample]:
        if self._reader is None:
            await self.start()
        if self._reader is None:
            logger.warning("TcpSource: no connection, stream is empty")
            return
        while self._running:
            raw = await self._reader.readline()
            if not raw:  # EOF
                logger.info("TcpSource: connection closed by peer")
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("TcpSource: bad JSON skipped: %s", exc)
                continue
            yield self._parse_payload(payload)
