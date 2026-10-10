"""Authentication subsystem.

Lightweight single-deployment auth for the dashboard: bcrypt-hashed passwords in
SQLite, stateless JWT (7-day expiry) carried in the ``Authorization: Bearer``
header (or a ``?token=`` query param for the WebSocket, which browsers cannot
header-stamp easily).

This is suitable for a clinical pilot / viva demo on a single deployment. A
production deployment would add SSO, password recovery, email verification, and
token revocation - none of which are implemented here, by design.
"""

from __future__ import annotations

from .dependencies import get_current_user
from .routes import router

__all__ = ["router", "get_current_user"]
