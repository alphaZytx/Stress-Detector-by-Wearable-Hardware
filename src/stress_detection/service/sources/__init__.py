"""Input source abstraction: one interface, four implementations.

Use build_source(cfg) to construct the source selected in config/service.yaml.
"""

from __future__ import annotations

from ..config import ServiceConfig
from .base import SensorSample, SensorSource, valid_bpm
from .csv_replay import CsvReplaySource
from .serial_source import SerialSource
from .synthetic import SyntheticSource
from .tcp_source import TcpSource

__all__ = [
    "SensorSample",
    "SensorSource",
    "valid_bpm",
    "SyntheticSource",
    "CsvReplaySource",
    "SerialSource",
    "TcpSource",
    "build_source",
]


def build_source(cfg: ServiceConfig) -> SensorSource:
    """Construct the configured input source."""
    match cfg.input.source:
        case "synthetic":
            return SyntheticSource(cfg.input.synthetic)
        case "csv_replay":
            return CsvReplaySource(cfg.input.csv_replay)
        case "serial":
            return SerialSource(cfg.input.serial)
        case "tcp":
            return TcpSource(cfg.input.tcp)
        case other:
            raise ValueError(
                f"Unknown input.source {other!r}; "
                "expected one of synthetic | csv_replay | serial | tcp"
            )
