"""Input source abstraction.

One interface with synthetic, CSV replay, serial, and TCP implementations.
The rest of the service consumes SensorSamples from this interface and does not
care which source is active.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import AsyncIterator

# Valid BPM range - must match stress_detection.io.cleaner (_BPM_LOW/_BPM_HIGH).
BPM_LOW = 40
BPM_HIGH = 200


@dataclass
class SensorSample:
    """One 1-Hz sample from the three-sensor wearable."""

    timestamp_ms: int        # service-relative wall-clock ms since stream start
    bpm: float | None        # None if invalid (out of [40,200] or sensor reports 0)
    avg_bpm: float | None
    temp_c: float | None
    gsr: float
    # source-specific metadata
    source_label: str | None = None   # only present from csv_replay

    def to_dict(self) -> dict:
        """JSON-serialisable view (used by the broadcaster and session manager)."""
        return asdict(self)


def valid_bpm(value: float | None) -> float | None:
    """Apply the Phase 1 BPM validity rule.

    Returns the value if it is inside [40, 200], otherwise None. A reported 0
    (PPG sensor init) falls outside the range and becomes None.
    """
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v < BPM_LOW or v > BPM_HIGH:
        return None
    return v


class SensorSource(ABC):
    """Async source of SensorSamples."""

    @abstractmethod
    async def stream(self) -> AsyncIterator[SensorSample]:
        """Yield SensorSamples at roughly the configured rate. Async generator."""
        ...

    @abstractmethod
    async def start(self) -> None:
        """Acquire resources (open files / ports / sockets)."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Release resources. Safe to call multiple times."""
        ...
