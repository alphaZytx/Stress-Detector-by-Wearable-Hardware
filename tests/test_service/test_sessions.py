import asyncio
import io
import json
import sqlite3
import zipfile

import pandas as pd

from stress_detection.service.inference.engine import Prediction
from stress_detection.service.sessions.manager import SessionManager
from stress_detection.service.sources.base import SensorSample


def _sample(i):
    return SensorSample(
        timestamp_ms=i * 1000,
        bpm=75.0 + i, avg_bpm=74.0, temp_c=36.5, gsr=100.0 + i,
        source_label="baseline",
    )


def _pred(i):
    return Prediction(
        timestamp_ms=i * 1000,
        label="stress", confidence=0.8,
        smoothed_label="stress", smoothed_confidence=0.75,
        raw_proba={"baseline": 0.2, "stress": 0.8},
    )


def _mgr(tmp_path):
    return SessionManager(tmp_path / "sessions.sqlite", tmp_path / "export")


def test_record_and_persist(tmp_path):
    async def run():
        mgr = _mgr(tmp_path)
        await mgr.initialize()
        sid = await mgr.start("unit-test", "notes")
        for i in range(50):
            pred = _pred(i) if i % 10 == 0 else None  # 5 predictions
            await mgr.record(_sample(i), None, pred)
        await mgr.stop()
        return sid, mgr

    sid, mgr = asyncio.run(run())

    conn = sqlite3.connect(mgr._db_path)
    assert conn.execute("SELECT COUNT(*) FROM samples WHERE session_id=?", (sid,)).fetchone()[0] == 50
    assert conn.execute("SELECT COUNT(*) FROM predictions WHERE session_id=?", (sid,)).fetchone()[0] == 5
    ended = conn.execute("SELECT ended_at_ms FROM sessions WHERE session_id=?", (sid,)).fetchone()[0]
    assert ended is not None
    conn.close()


def test_record_noop_without_active_session(tmp_path):
    async def run():
        mgr = _mgr(tmp_path)
        await mgr.initialize()
        await mgr.record(_sample(0), None, None)  # no active session → ignored
        conn = sqlite3.connect(mgr._db_path)
        n = conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
        conn.close()
        return n

    assert asyncio.run(run()) == 0


def test_export_json_structure(tmp_path):
    async def run():
        mgr = _mgr(tmp_path)
        await mgr.initialize()
        sid = await mgr.start("export-test", None)
        for i in range(10):
            await mgr.record(_sample(i), None, _pred(i))
        await mgr.add_label(3000, "stress")
        await mgr.stop()
        return sid, await mgr.export(sid, "json")

    sid, path = asyncio.run(run())
    assert path.exists()
    payload = json.loads(path.read_text())
    assert payload["session_id"] == sid
    assert payload["user_label"] == "export-test"
    assert len(payload["samples"]) == 10
    assert len(payload["predictions"]) == 10
    assert len(payload["labels"]) == 1
    for key in ("started_at_ms", "ended_at_ms"):
        assert key in payload


def test_export_csv_has_source_column(tmp_path):
    async def run():
        mgr = _mgr(tmp_path)
        await mgr.initialize()
        sid = await mgr.start("csv-test", None)
        for i in range(5):
            await mgr.record(_sample(i), None, _pred(i))
        await mgr.stop()
        return await mgr.export(sid, "csv")

    path = asyncio.run(run())
    df = pd.read_csv(path)
    assert "source" in df.columns
    assert set(df["source"].unique()) >= {"sample", "prediction"}


def test_export_missing_session_raises(tmp_path):
    async def run():
        mgr = _mgr(tmp_path)
        await mgr.initialize()
        await mgr.export("does-not-exist", "json")

    import pytest
    with pytest.raises(FileNotFoundError):
        asyncio.run(run())


def test_calibration_roundtrip(tmp_path):
    async def run():
        mgr = _mgr(tmp_path)
        await mgr.initialize()
        payload = {"gsr_baseline": 66.0, "hr_baseline": 72.0, "extra": {"hand": "left"}}
        await mgr.set_calibration("user-7", payload)
        return await mgr.get_calibration("user-7")

    row = asyncio.run(run())
    assert row is not None
    assert row["user_id"] == "user-7"
    assert row["gsr_baseline"] == 66.0
    assert row["hr_baseline"] == 72.0
    assert json.loads(row["payload_json"])["extra"]["hand"] == "left"


def test_list_sessions(tmp_path):
    async def run():
        mgr = _mgr(tmp_path)
        await mgr.initialize()
        await mgr.start("s1", None)
        await mgr.stop()
        await mgr.start("s2", None)
        await mgr.stop()
        return await mgr.list_sessions()

    sessions = asyncio.run(run())
    assert len(sessions) == 2
    assert {s["user_label"] for s in sessions} == {"s1", "s2"}


def test_list_sessions_scoped_by_user(tmp_path):
    async def run():
        mgr = _mgr(tmp_path)
        await mgr.initialize()
        await mgr.start("a", None, user_id="u1")
        await mgr.stop()
        await mgr.start("b", None, user_id="u2")
        await mgr.stop()
        return await mgr.list_sessions(user_id="u1")

    sessions = asyncio.run(run())
    assert len(sessions) == 1
    assert sessions[0]["user_label"] == "a"
    assert sessions[0]["user_id"] == "u1"


def test_delete_session_removes_all_rows(tmp_path):
    async def run():
        mgr = _mgr(tmp_path)
        await mgr.initialize()
        sid = await mgr.start("del", None)
        for i in range(5):
            await mgr.record(_sample(i), None, _pred(i))
        await mgr.add_label(1000, "stress")
        await mgr.stop()
        deleted = await mgr.delete_session(sid)
        missing = await mgr.delete_session("not-real")
        return sid, deleted, missing, mgr

    sid, deleted, missing, mgr = asyncio.run(run())
    assert deleted is True
    assert missing is False
    conn = sqlite3.connect(mgr._db_path)
    for table in ("sessions", "samples", "predictions", "labels"):
        n = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE session_id=?", (sid,)
        ).fetchone()[0]
        assert n == 0, f"{table} still has rows"
    conn.close()


def test_delete_session_is_scoped_to_owner(tmp_path):
    """A user_id mismatch must behave exactly like a missing session - this is
    the regression test for the IDOR where any authenticated user could delete
    any other user's session by guessing its id."""
    async def run():
        mgr = _mgr(tmp_path)
        await mgr.initialize()
        sid = await mgr.start("mine", None, user_id="owner")
        await mgr.stop()
        wrong_owner = await mgr.delete_session(sid, user_id="attacker")
        right_owner = await mgr.delete_session(sid, user_id="owner")
        return wrong_owner, right_owner

    wrong_owner, right_owner = asyncio.run(run())
    assert wrong_owner is False, "deleted a session belonging to a different user"
    assert right_owner is True


def test_export_is_scoped_to_owner(tmp_path):
    """Same IDOR, for export: a non-owner must get the same FileNotFoundError
    as a nonexistent session, not the real owner's data."""
    async def run():
        mgr = _mgr(tmp_path)
        await mgr.initialize()
        sid = await mgr.start("mine", None, user_id="owner")
        await mgr.record(_sample(0), None, _pred(0))
        await mgr.stop()
        return mgr, sid

    mgr, sid = asyncio.run(run())

    import pytest
    with pytest.raises(FileNotFoundError):
        asyncio.run(mgr.export(sid, "json", user_id="attacker"))

    # The rightful owner can still export it.
    path = asyncio.run(mgr.export(sid, "json", user_id="owner"))
    assert path.exists()


def test_add_label_to_past_session(tmp_path):
    """add_label targets an explicit session_id even when it isn't active (the
    History-view annotation path)."""
    async def run():
        mgr = _mgr(tmp_path)
        await mgr.initialize()
        sid = await mgr.start("past", None)
        await mgr.stop()  # session no longer active
        ok_targeted = await mgr.add_label(5000, "manual-stress", session_id=sid)
        ok_none = await mgr.add_label(6000, "orphan")  # no active, no id
        data = await mgr._fetch_session_data(sid)
        return ok_targeted, ok_none, data["labels"]

    ok_targeted, ok_none, labels = asyncio.run(run())
    assert ok_targeted is True
    assert ok_none is False
    assert len(labels) == 1
    assert labels[0]["label"] == "manual-stress"
    assert labels[0]["timestamp_ms"] == 5000


def test_export_all_zip_scoped_to_user(tmp_path):
    async def run():
        mgr = _mgr(tmp_path)
        await mgr.initialize()
        s1 = await mgr.start("u1-a", None, user_id="u1")
        for i in range(3):
            await mgr.record(_sample(i), None, _pred(i))
        await mgr.stop()
        s2 = await mgr.start("u1-b", None, user_id="u1")
        await mgr.stop()
        await mgr.start("u2-a", None, user_id="u2")
        await mgr.stop()
        return s1, s2, await mgr.export_all_zip(user_id="u1")

    s1, s2, blob = asyncio.run(run())
    zf = zipfile.ZipFile(io.BytesIO(blob))
    names = set(zf.namelist())
    assert names == {f"{s1}.json", f"{s2}.json"}  # only u1's sessions
    payload = json.loads(zf.read(f"{s1}.json"))
    assert payload["user_label"] == "u1-a"
    assert len(payload["samples"]) == 3


def _pred_labeled(i, smoothed):
    p_stress = 0.8 if smoothed == "stress" else 0.2
    return Prediction(
        timestamp_ms=i * 1000,
        label=smoothed, confidence=0.8,
        smoothed_label=smoothed, smoothed_confidence=0.75,
        raw_proba={"baseline": 1 - p_stress, "stress": p_stress},
    )


def test_session_summaries_dominant_state(tmp_path):
    """session_summaries computes the dominant smoothed state + share per session
    in one query, scoped to the user, and handles empty sessions."""
    async def run():
        mgr = _mgr(tmp_path)
        await mgr.initialize()

        # Session A: 3 stress + 1 baseline prediction → dominant stress @ 75%.
        sa = await mgr.start("A", None, user_id="u1")
        labels_a = ["stress", "stress", "stress", "baseline"]
        for i, lab in enumerate(labels_a):
            await mgr.record(_sample(i), None, _pred_labeled(i, lab))
        await mgr.stop()

        # Session B: 2 baseline predictions → dominant baseline @ 100%.
        sb = await mgr.start("B", None, user_id="u1")
        for i, lab in enumerate(["baseline", "baseline"]):
            await mgr.record(_sample(i), None, _pred_labeled(i, lab))
        await mgr.stop()

        # Session C: no predictions (samples only) → dominant_state None.
        sc = await mgr.start("C", None, user_id="u1")
        await mgr.record(_sample(0), None, None)
        await mgr.stop()

        # Another user's session must not appear.
        await mgr.start("other", None, user_id="u2")
        await mgr.record(_sample(0), None, _pred_labeled(0, "stress"))
        await mgr.stop()

        return sa, sb, sc, await mgr.session_summaries(user_id="u1")

    sa, sb, sc, summaries = asyncio.run(run())
    by_id = {s["session_id"]: s for s in summaries}
    assert set(by_id) == {sa, sb, sc}  # u2's session excluded

    assert by_id[sa]["dominant_state"] == "stress"
    assert by_id[sa]["dominant_state_pct"] == 0.75
    assert by_id[sa]["user_label"] == "A"

    assert by_id[sb]["dominant_state"] == "baseline"
    assert by_id[sb]["dominant_state_pct"] == 1.0

    assert by_id[sc]["dominant_state"] is None
    assert by_id[sc]["dominant_state_pct"] == 0.0


def test_clear_calibration(tmp_path):
    async def run():
        mgr = _mgr(tmp_path)
        await mgr.initialize()
        await mgr.set_calibration("u9", {"hr_baseline": 70.0, "temp_baseline": 33.0})
        before = await mgr.get_calibration("u9")
        cleared = await mgr.clear_calibration("u9")
        after = await mgr.get_calibration("u9")
        again = await mgr.clear_calibration("u9")
        return before, cleared, after, again

    before, cleared, after, again = asyncio.run(run())
    assert before is not None and before["temp_baseline"] == 33.0
    assert cleared is True
    assert after is None
    assert again is False
