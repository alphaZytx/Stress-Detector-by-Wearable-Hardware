"""WebSocket broadcaster - fans raw samples, features, and predictions out to
every connected client.

Three message types are pushed (see HANDOFF for the exact JSON the frontend
consumes):
  {"type": "sample",     "data": <SensorSample dict>}
  {"type": "features",   "data": <feature dict>, "timestamp_ms": <int>}
  {"type": "prediction", "data": <Prediction dict>}

A client that errors on send (slow/disconnected) is dropped silently - one bad
client never blocks the stream for the others.
"""

from __future__ import annotations

import logging

from fastapi import WebSocket

from ..inference.engine import Prediction
from ..sources.base import SensorSample

logger = logging.getLogger(__name__)


class WebSocketBroadcaster:
    def __init__(self):
        self._clients: set[WebSocket] = set()

    async def add_client(self, ws: WebSocket) -> None:
        self._clients.add(ws)
        logger.info("WS client connected (total=%d)", len(self._clients))

    async def remove_client(self, ws: WebSocket) -> None:
        self._clients.discard(ws)
        logger.info("WS client disconnected (total=%d)", len(self._clients))

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def _broadcast(self, message: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - drop slow/broken clients silently
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)
        if dead:
            logger.debug("Dropped %d unreachable WS client(s)", len(dead))

    async def push_sample(self, sample: SensorSample) -> None:
        await self._broadcast({"type": "sample", "data": sample.to_dict()})

    async def push_prediction(self, features: dict, pred: Prediction | None) -> None:
        ts = pred.timestamp_ms if pred is not None else None
        await self._broadcast(
            {"type": "features", "data": features, "timestamp_ms": ts}
        )
        if pred is not None:
            await self._broadcast({"type": "prediction", "data": pred.model_dump()})
