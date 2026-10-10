"""Logging configuration for the service.

Uses stdlib logging with a compact key=value-ish format that is easy to grep
and read in a terminal. Called once at app startup. No print() in service code.
"""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False

_FORMAT = "%(asctime)s level=%(levelname)s logger=%(name)s msg=%(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S"


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger once. Idempotent across repeated calls."""
    global _CONFIGURED
    numeric = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric)

    if not _CONFIGURED:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
        root.addHandler(handler)
        _CONFIGURED = True
    else:
        for handler in root.handlers:
            handler.setLevel(numeric)
