"""JWT encode/decode (HS256) for stateless session tokens.

Secret comes from the ``STRESS_JWT_SECRET`` env var. A dev fallback is provided
so the demo runs out-of-the-box, but a LOUD warning is logged once when it is
used - never ship the fallback to a real deployment.

Token expiry is 7 days. This is a demo, not a bank; long expiry keeps the viva
demo from logging out mid-session.
"""

from __future__ import annotations

import logging
import os
import time

import jwt

logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"
_DEV_FALLBACK_SECRET = "dev-insecure-stress-detection-secret-change-me"  # noqa: S105
TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days

_warned_fallback = False


def _secret() -> str:
    global _warned_fallback
    secret = os.environ.get("STRESS_JWT_SECRET")
    if secret:
        return secret
    if not _warned_fallback:
        logger.warning(
            "=" * 70 + "\n"
            "STRESS_JWT_SECRET is not set - using an INSECURE dev fallback secret.\n"
            "Anyone can forge tokens. Set STRESS_JWT_SECRET before any real use.\n"
            + "=" * 70
        )
        _warned_fallback = True
    return _DEV_FALLBACK_SECRET


def create_token(user_id: str, email: str) -> tuple[str, int]:
    """Return (jwt, expires_at_ms). ``sub`` is the user_id."""
    now = int(time.time())
    exp = now + TOKEN_TTL_SECONDS
    payload = {"sub": user_id, "email": email, "iat": now, "exp": exp}
    token = jwt.encode(payload, _secret(), algorithm=_ALGORITHM)
    return token, exp * 1000


class TokenError(Exception):
    """Raised when a token is missing, malformed, expired, or has a bad signature."""


def decode_token(token: str) -> dict:
    """Decode + verify a token. Raises TokenError on any failure."""
    try:
        return jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("invalid token") from exc
