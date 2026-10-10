"""Public demo-session endpoint."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()

# service/demo → service → stress_detection → src → repo root
_REPO_ROOT = Path(__file__).parents[4]
_DEMO_PATH = _REPO_ROOT / "data" / "demo" / "canned_session.json"


@lru_cache(maxsize=1)
def _load_demo() -> dict:
    if not _DEMO_PATH.exists():
        raise FileNotFoundError(_DEMO_PATH)
    return json.loads(_DEMO_PATH.read_text())


@router.get("/demo/session")
async def demo_session() -> dict:
    """Return the canned demo session JSON. Public (no auth) so demo mode works
    without login."""
    try:
        return _load_demo()
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Demo session asset not found. Run scripts/build_demo_session.py.",
        )
