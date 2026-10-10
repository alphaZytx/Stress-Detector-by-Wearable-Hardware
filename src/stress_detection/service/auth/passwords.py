"""Password hashing via bcrypt (passlib).

bcrypt has a hard 72-byte limit on the input; we truncate defensively before
hashing/verifying so very long passwords don't raise (passlib 1.7.4 + bcrypt 4.x
behaviour). 72 bytes is far beyond any sane password length.
"""

from __future__ import annotations

from passlib.context import CryptContext

_BCRYPT_MAX_BYTES = 72

_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _clamp(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) <= _BCRYPT_MAX_BYTES:
        return password
    return encoded[:_BCRYPT_MAX_BYTES].decode("utf-8", errors="ignore")


def hash_password(password: str) -> str:
    return _ctx.hash(_clamp(password))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ctx.verify(_clamp(password), password_hash)
    except ValueError:
        # Malformed stored hash - treat as a failed verification, never raise.
        return False
