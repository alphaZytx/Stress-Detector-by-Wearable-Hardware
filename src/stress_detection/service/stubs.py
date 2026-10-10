"""No-op stubs for components implemented in later subphases.

Used by the Runtime/lifespan so the pipeline can run end-to-end before the real
InferenceEngine (2.4), WebSocketBroadcaster (2.5), and SessionManager (2.6)
land. Each satisfies the minimal interface the Runtime calls.
"""

from __future__ import annotations

from .sources.base import SensorSample


class NullEngine:
    """Stand-in inference engine - returns no prediction."""

    def predict(self, features: dict, timestamp_ms: int = 0):  # noqa: D401, ANN201
        return None


class NullBroadcaster:
    """Stand-in broadcaster - drops everything."""

    async def push_sample(self, sample: SensorSample) -> None:
        return None

    async def push_prediction(self, features: dict, pred) -> None:
        return None


class NullSessionMgr:
    """Stand-in session manager - endpoints respond, but nothing is persisted.

    Satisfies the full interface the control endpoints call so 2.5 works before
    the real SQLite SessionManager lands in 2.6. start() returns a real uuid so
    /session/start responds with an id; everything else is a no-op/empty.
    """

    def __init__(self):
        self._active: str | None = None

    async def initialize(self) -> None:
        return None

    async def start(self, user_label: str | None, notes: str | None) -> str:
        import uuid
        self._active = str(uuid.uuid4())
        return self._active

    async def stop(self) -> str | None:
        sid, self._active = self._active, None
        return sid

    async def record(self, sample: SensorSample, features: dict | None, pred) -> None:
        return None

    async def add_label(self, timestamp_ms: int, label: str) -> None:
        return None

    async def list_sessions(self) -> list[dict]:
        return []

    async def export(self, session_id: str, fmt: str):
        # Nothing persisted in the stub - signal not-found so the endpoint 404s.
        raise FileNotFoundError(session_id)

    async def set_calibration(self, user_id: str, payload: dict) -> None:
        return None

    async def get_calibration(self, user_id: str) -> dict | None:
        return None
