"""Uvicorn entry point for the stress-detection inference service.

Usage:
    python3 scripts/run_service.py

Host/port/log level come from config/service.yaml.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

import uvicorn

from stress_detection.service.app import create_app
from stress_detection.service.config import get_service_config


def main() -> None:
    cfg = get_service_config()
    uvicorn.run(
        create_app(cfg),
        host=cfg.service.host,
        port=cfg.service.port,
        log_level=cfg.service.log_level.lower(),
    )


if __name__ == "__main__":
    main()
