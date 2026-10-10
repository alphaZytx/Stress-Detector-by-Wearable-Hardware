"""SQLite-backed user store (aiosqlite).

Shares the same database file as the SessionManager so the whole deployment is a
single .sqlite file. Connections are opened per-operation, matching the
SessionManager's style.
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    created_at_ms INTEGER NOT NULL
);
"""


def _now_ms() -> int:
    return int(time.time() * 1000)


class EmailTakenError(Exception):
    """Raised when registering an email that already exists."""


class UserDb:
    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(_SCHEMA)
            await db.commit()
        logger.info("UserDb initialised db=%s", self._db_path)

    async def create_user(
        self, email: str, password_hash: str, display_name: str | None
    ) -> dict:
        user_id = str(uuid.uuid4())
        created = _now_ms()
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "INSERT INTO users (user_id, email, password_hash, "
                    "display_name, created_at_ms) VALUES (?,?,?,?,?)",
                    (user_id, email.lower(), password_hash, display_name, created),
                )
                await db.commit()
        except aiosqlite.IntegrityError as exc:
            raise EmailTakenError(email) from exc
        logger.info("User created %s (%s)", user_id, email)
        return {
            "user_id": user_id,
            "email": email.lower(),
            "display_name": display_name,
            "created_at_ms": created,
        }

    async def get_by_email(self, email: str) -> dict | None:
        return await self._fetch_one("email", email.lower())

    async def get_by_id(self, user_id: str) -> dict | None:
        return await self._fetch_one("user_id", user_id)

    async def _fetch_one(self, column: str, value: str) -> dict | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT * FROM users WHERE {column} = ?", (value,)
            ) as cur:
                row = await cur.fetchone()
        return dict(row) if row is not None else None
