"""SQLite-backed session manager (aiosqlite).

Persists samples + predictions + user labels per recording session so the
dashboard can replay past sessions, plus per-user calibration baselines.

Connections are opened per-operation (no global handle), per the Phase 2 brief.

Deviation (documented): __init__ also takes ``export_dir`` so export() knows
where to write - the prompt's signature showed only db_path but export()'s spec
requires config.session.export_dir.
"""

from __future__ import annotations

import io
import json
import logging
import time
import uuid
import zipfile
from pathlib import Path
from typing import Literal

import aiosqlite
import pandas as pd

from ..inference.engine import Prediction
from ..sources.base import SensorSample

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _now_ms() -> int:
    return int(time.time() * 1000)


class SessionManager:
    def __init__(self, db_path: Path, export_dir: Path):
        self._db_path = Path(db_path)
        self._export_dir = Path(export_dir)
        self._active_session: str | None = None

    @property
    def active_session(self) -> str | None:
        return self._active_session

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._export_dir.mkdir(parents=True, exist_ok=True)
        schema = _SCHEMA_PATH.read_text()
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(schema)
            await self._migrate(db)
            await db.commit()
        logger.info("SessionManager initialised db=%s", self._db_path)

    @staticmethod
    async def _migrate(db: aiosqlite.Connection) -> None:
        """Add columns introduced after a DB was first created.

        SQLite's CREATE TABLE IF NOT EXISTS won't add columns to a table that
        already exists, so older databases need explicit ALTER TABLE. Each is
        guarded by a column-presence check so it's idempotent.
        """
        async def cols(table: str) -> set[str]:
            async with db.execute(f"PRAGMA table_info({table})") as cur:
                return {r[1] for r in await cur.fetchall()}

        session_cols = await cols("sessions")
        if "user_id" not in session_cols:
            await db.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
        if "use_calibration" not in session_cols:
            await db.execute(
                "ALTER TABLE sessions ADD COLUMN use_calibration INTEGER DEFAULT 1"
            )
        if "temp_baseline" not in await cols("calibrations"):
            await db.execute("ALTER TABLE calibrations ADD COLUMN temp_baseline REAL")

        # Remove columns from the retired hardware contract when opening a
        # database created by an earlier project version. Session timestamps,
        # heart rate, GSR, temperature, predictions, and labels are preserved.
        sample_cols = await cols("samples")
        retired = (
            "ax", "ay", "az", "gx", "gy", "gz",
            "motion_magnitude", "motion_flag", "leads_off",
        )
        for column in retired:
            if column in sample_cols:
                await db.execute(f"ALTER TABLE samples DROP COLUMN {column}")

    async def start(
        self,
        user_label: str | None,
        notes: str | None,
        user_id: str | None = None,
        use_calibration: bool = True,
    ) -> str:
        session_id = str(uuid.uuid4())
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO sessions (session_id, started_at_ms, user_label, "
                "notes, user_id, use_calibration) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, _now_ms(), user_label, notes, user_id, int(use_calibration)),
            )
            await db.commit()
        self._active_session = session_id
        logger.info(
            "Session started %s (label=%s user=%s calib=%s)",
            session_id, user_label, user_id, use_calibration,
        )
        return session_id

    async def stop(self) -> str | None:
        if self._active_session is None:
            return None
        sid = self._active_session
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE sessions SET ended_at_ms = ? WHERE session_id = ?",
                (_now_ms(), sid),
            )
            await db.commit()
        self._active_session = None
        logger.info("Session stopped %s", sid)
        return sid

    async def record(
        self,
        sample: SensorSample,
        features: dict | None,
        pred: Prediction | None,
    ) -> None:
        # No-op unless a session is active. features are not persisted (no table);
        # they are derived from samples and used only for inference.
        if self._active_session is None:
            return
        sid = self._active_session
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO samples (session_id, timestamp_ms, bpm, "
                "avg_bpm, temp_c, gsr) VALUES (?,?,?,?,?,?)",
                (
                    sid, sample.timestamp_ms, sample.bpm, sample.avg_bpm,
                    sample.temp_c, sample.gsr,
                ),
            )
            if pred is not None:
                await db.execute(
                    "INSERT OR IGNORE INTO predictions (session_id, timestamp_ms, "
                    "label, confidence, smoothed_label, smoothed_confidence, "
                    "p_baseline, p_stress) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        sid, pred.timestamp_ms, pred.label, pred.confidence,
                        pred.smoothed_label, pred.smoothed_confidence,
                        pred.raw_proba.get("baseline"), pred.raw_proba.get("stress"),
                    ),
                )
            await db.commit()

    async def add_label(
        self, timestamp_ms: int, label: str, session_id: str | None = None
    ) -> bool:
        """Attach a label at a timestamp. Targets ``session_id`` if given (used by
        the History view to annotate a PAST session), else the active session.
        Returns True if a session was targeted, False if there was nothing to
        attach to."""
        target = session_id or self._active_session
        if target is None:
            logger.warning("add_label ignored: no session_id and no active session")
            return False
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO labels (session_id, timestamp_ms, label) "
                "VALUES (?, ?, ?)",
                (target, timestamp_ms, label),
            )
            await db.commit()
        return True

    async def list_sessions(self, user_id: str | None = None) -> list[dict]:
        query = (
            "SELECT session_id, started_at_ms, ended_at_ms, user_label, notes, "
            "user_id FROM sessions"
        )
        params: tuple = ()
        if user_id is not None:
            query += " WHERE user_id = ?"
            params = (user_id,)
        query += " ORDER BY started_at_ms"
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cur:
                rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def session_summaries(self, user_id: str | None = None) -> list[dict]:
        """Lightweight per-session summaries for the History list.

        Computes each session's dominant smoothed state and its share directly
        from the predictions table in a SINGLE query (one round trip), avoiding
        the N+1 full-export fetch the History view previously did per row.

        Returns one dict per session:
          {session_id, started_at_ms, ended_at_ms, user_label, notes,
           dominant_state: "baseline"|"stress"|None, dominant_state_pct: float}
        dominant_state is None (and pct 0.0) for sessions with no predictions.
        (notes is included so the History list renders fully in one round trip.)
        """
        query = (
            "SELECT s.session_id, s.started_at_ms, s.ended_at_ms, s.user_label, "
            "s.notes, p.smoothed_label AS state, COUNT(p.smoothed_label) AS cnt "
            "FROM sessions s LEFT JOIN predictions p "
            "ON s.session_id = p.session_id"
        )
        params: tuple = ()
        if user_id is not None:
            query += " WHERE s.user_id = ?"
            params = (user_id,)
        query += " GROUP BY s.session_id, p.smoothed_label ORDER BY s.started_at_ms"

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cur:
                rows = [dict(r) for r in await cur.fetchall()]

        # Fold the (session, state)-grouped rows into one summary per session.
        acc: dict[str, dict] = {}
        for r in rows:
            sid = r["session_id"]
            s = acc.setdefault(
                sid,
                {
                    "session_id": sid,
                    "started_at_ms": r["started_at_ms"],
                    "ended_at_ms": r["ended_at_ms"],
                    "user_label": r["user_label"],
                    "notes": r["notes"],
                    "_counts": {},
                    "_total": 0,
                },
            )
            state = r["state"]
            if state is not None:  # LEFT JOIN yields a NULL state for empty sessions
                s["_counts"][state] = s["_counts"].get(state, 0) + r["cnt"]
                s["_total"] += r["cnt"]

        summaries = []
        for s in acc.values():
            counts = s.pop("_counts")
            total = s.pop("_total")
            if total > 0:
                dominant = max(counts, key=counts.get)
                s["dominant_state"] = dominant
                s["dominant_state_pct"] = round(counts[dominant] / total, 4)
            else:
                s["dominant_state"] = None
                s["dominant_state_pct"] = 0.0
            summaries.append(s)
        return summaries

    async def delete_session(self, session_id: str, user_id: str | None = None) -> bool:
        """Delete a session and all its samples/predictions/labels. Returns True
        if a session row existed, belonged to `user_id` (when given), and was
        removed.

        `user_id` is optional only so internal/admin callers can omit it; every
        REST route passes the caller's own user_id, so one user can never
        delete another user's session by guessing its id.
        """
        async with aiosqlite.connect(self._db_path) as db:
            if user_id is not None:
                cur = await db.execute(
                    "SELECT 1 FROM sessions WHERE session_id = ? AND user_id = ?",
                    (session_id, user_id),
                )
            else:
                cur = await db.execute(
                    "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
                )
            exists = await cur.fetchone() is not None
            if not exists:
                return False
            for table in ("samples", "predictions", "labels", "sessions"):
                await db.execute(
                    f"DELETE FROM {table} WHERE session_id = ?", (session_id,)
                )
            await db.commit()
        if self._active_session == session_id:
            self._active_session = None
        logger.info("Session deleted %s", session_id)
        return True

    async def _fetch_session_data(self, session_id: str, user_id: str | None = None) -> dict:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            if user_id is not None:
                query = "SELECT * FROM sessions WHERE session_id = ? AND user_id = ?"
                params: tuple = (session_id, user_id)
            else:
                query = "SELECT * FROM sessions WHERE session_id = ?"
                params = (session_id,)
            async with db.execute(query, params) as cur:
                session_row = await cur.fetchone()
            if session_row is None:
                raise FileNotFoundError(session_id)

            async def fetch(table: str) -> list[dict]:
                columns = (
                    "session_id, timestamp_ms, bpm, avg_bpm, temp_c, gsr"
                    if table == "samples" else "*"
                )
                async with db.execute(
                    f"SELECT {columns} FROM {table} WHERE session_id = ? ORDER BY timestamp_ms",
                    (session_id,),
                ) as c:
                    return [dict(r) for r in await c.fetchall()]

            return {
                "session": dict(session_row),
                "samples": await fetch("samples"),
                "predictions": await fetch("predictions"),
                "labels": await fetch("labels"),
            }

    async def export(
        self,
        session_id: str,
        fmt: Literal["json", "csv"] = "json",
        user_id: str | None = None,
    ) -> Path:
        """Export a session. Raises FileNotFoundError if the session does not
        exist OR belongs to a different user than `user_id` (when given) - the
        two cases are deliberately indistinguishable to the caller, so probing
        for another user's session id can't be used to enumerate valid ids."""
        data = await self._fetch_session_data(session_id, user_id=user_id)
        self._export_dir.mkdir(parents=True, exist_ok=True)
        session = data["session"]

        if fmt == "json":
            out = self._export_dir / f"{session_id}.json"
            payload = {
                "session_id": session["session_id"],
                "started_at_ms": session["started_at_ms"],
                "ended_at_ms": session["ended_at_ms"],
                "user_label": session["user_label"],
                "notes": session["notes"],
                "samples": data["samples"],
                "predictions": data["predictions"],
                "labels": data["labels"],
            }
            out.write_text(json.dumps(payload, indent=2))
            return out

        # CSV: one file, a `source` column distinguishes sample/prediction/label rows.
        out = self._export_dir / f"{session_id}.csv"
        frames = []
        for source in ("samples", "predictions", "labels"):
            if data[source]:
                df = pd.DataFrame(data[source])
                df.insert(0, "source", source[:-1])  # "sample"/"prediction"/"label"
                frames.append(df)
        if frames:
            pd.concat(frames, ignore_index=True).to_csv(out, index=False)
        else:
            out.write_text("source,timestamp_ms\n")
        return out

    @staticmethod
    def _json_payload(data: dict) -> dict:
        session = data["session"]
        return {
            "session_id": session["session_id"],
            "started_at_ms": session["started_at_ms"],
            "ended_at_ms": session["ended_at_ms"],
            "user_label": session["user_label"],
            "notes": session["notes"],
            "samples": data["samples"],
            "predictions": data["predictions"],
            "labels": data["labels"],
        }

    async def export_all_zip(self, user_id: str | None = None) -> bytes:
        """Build an in-memory ZIP of one JSON per session (scoped to user_id if
        given). Returns the ZIP bytes; the route streams them as a download."""
        sessions = await self.list_sessions(user_id=user_id)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for s in sessions:
                data = await self._fetch_session_data(s["session_id"], user_id=user_id)
                payload = self._json_payload(data)
                zf.writestr(
                    f"{s['session_id']}.json", json.dumps(payload, indent=2)
                )
        return buf.getvalue()

    async def set_calibration(self, user_id: str, payload: dict) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO calibrations (user_id, gsr_baseline, "
                "hr_baseline, temp_baseline, captured_at_ms, payload_json) "
                "VALUES (?,?,?,?,?,?)",
                (
                    user_id,
                    payload.get("gsr_baseline"),
                    payload.get("hr_baseline"),
                    payload.get("temp_baseline"),
                    _now_ms(),
                    json.dumps(payload),
                ),
            )
            await db.commit()
        logger.info("Calibration stored for user %s", user_id)

    async def get_calibration(self, user_id: str) -> dict | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM calibrations WHERE user_id = ?", (user_id,)
            ) as cur:
                row = await cur.fetchone()
        return dict(row) if row is not None else None

    async def clear_calibration(self, user_id: str) -> bool:
        """Remove a user's calibration. Returns True if a row was deleted."""
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                "DELETE FROM calibrations WHERE user_id = ?", (user_id,)
            )
            await db.commit()
            deleted = cur.rowcount > 0
        if deleted:
            logger.info("Calibration cleared for user %s", user_id)
        return deleted
