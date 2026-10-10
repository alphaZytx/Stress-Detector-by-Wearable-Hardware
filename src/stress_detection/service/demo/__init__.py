"""Canned demo-session asset + public endpoint.

Serves a pre-recorded baseline→stress→breathing-recovery→baseline session so the
dashboard's demo mode works without a wearable or a login (useful for placement
interviews). Generated offline by scripts/build_demo_session.py.
"""

from __future__ import annotations

from .routes import router

__all__ = ["router"]
