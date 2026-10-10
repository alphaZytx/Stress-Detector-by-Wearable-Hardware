from fastapi.testclient import TestClient

from .conftest import auth_headers, register_and_token


def test_ws_requires_token(service_app):
    with TestClient(service_app) as client:
        # No token → server accepts then closes with 4401.
        with client.websocket_connect("/ws/stream") as ws:
            import pytest
            from starlette.websockets import WebSocketDisconnect

            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()
            assert exc.value.code == 4401


def test_ws_stream_receives_message(service_app):
    with TestClient(service_app) as client:
        token = register_and_token(client)
        with client.websocket_connect(f"/ws/stream?token={token}") as ws:
            msg = ws.receive_json()
            assert msg["type"] in ("sample", "features", "prediction")
            assert "data" in msg


def test_ws_stream_eventually_sends_sample(service_app):
    with TestClient(service_app) as client:
        token = register_and_token(client)
        with client.websocket_connect(f"/ws/stream?token={token}") as ws:
            seen_types = set()
            for _ in range(40):
                msg = ws.receive_json()
                seen_types.add(msg["type"])
                if "sample" in seen_types:
                    break
            assert "sample" in seen_types


def test_session_requires_auth(service_app):
    with TestClient(service_app) as client:
        resp = client.post("/session/start", json={"user_label": "x"})
        assert resp.status_code == 401


def test_session_start_returns_id(service_app):
    with TestClient(service_app) as client:
        h = auth_headers(client)
        resp = client.post(
            "/session/start", json={"user_label": "test", "notes": "n"}, headers=h
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "session_id" in body and body["session_id"]


def test_session_stop_returns_id(service_app):
    with TestClient(service_app) as client:
        h = auth_headers(client)
        client.post("/session/start", json={"user_label": "x"}, headers=h)
        resp = client.post("/session/stop", headers=h)
        assert resp.status_code == 200
        assert "session_id" in resp.json()


def test_session_label_ok(service_app):
    with TestClient(service_app) as client:
        h = auth_headers(client)
        client.post("/session/start", json={"user_label": "x"}, headers=h)
        resp = client.post(
            "/session/label", json={"timestamp_ms": 1000, "label": "stress"}, headers=h
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_session_list_returns_list(service_app):
    with TestClient(service_app) as client:
        resp = client.get("/session/list", headers=auth_headers(client))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def test_session_summaries_returns_list(service_app):
    with TestClient(service_app) as client:
        h = auth_headers(client)
        client.post("/session/start", json={"user_label": "sum"}, headers=h)
        client.post("/session/stop", headers=h)
        resp = client.get("/session/summaries", headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list) and len(body) == 1
        row = body[0]
        # Schema keys present; no predictions yet → dominant_state is None.
        assert set(row) >= {
            "session_id", "started_at_ms", "ended_at_ms",
            "user_label", "dominant_state", "dominant_state_pct",
        }
        assert row["user_label"] == "sum"
        assert row["dominant_state"] is None


def test_session_summaries_requires_auth(service_app):
    with TestClient(service_app) as client:
        assert client.get("/session/summaries").status_code == 401


def test_session_summaries_scoped_to_user(service_app):
    with TestClient(service_app) as client:
        h1 = auth_headers(client)
        h2 = auth_headers(client)
        client.post("/session/start", json={"user_label": "mine"}, headers=h1)
        client.post("/session/stop", headers=h1)
        assert client.get("/session/summaries", headers=h2).json() == []
        assert len(client.get("/session/summaries", headers=h1).json()) == 1


def test_calibration_ok(service_app):
    with TestClient(service_app) as client:
        h = auth_headers(client)
        resp = client.post(
            "/calibration",
            json={"gsr_baseline": 66.0, "hr_baseline": 72.0, "temp_baseline": 33.0},
            headers=h,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok" and body["user_id"]


def test_export_missing_session_404(service_app):
    with TestClient(service_app) as client:
        resp = client.get("/session/nope/export", headers=auth_headers(client))
        assert resp.status_code == 404


def test_delete_session_roundtrip(service_app):
    with TestClient(service_app) as client:
        h = auth_headers(client)
        sid = client.post(
            "/session/start", json={"user_label": "x"}, headers=h
        ).json()["session_id"]
        client.post("/session/stop", headers=h)
        ok = client.delete(f"/session/{sid}", headers=h)
        assert ok.status_code == 200 and ok.json() == {"status": "ok"}
        again = client.delete(f"/session/{sid}", headers=h)
        assert again.status_code == 404


def test_delete_session_rejects_a_different_user(service_app):
    """Regression test for an IDOR: delete_session previously took only a
    session_id with no ownership check, so any authenticated user could
    delete any other user's session by guessing its UUID."""
    with TestClient(service_app) as client:
        owner = auth_headers(client)
        attacker = auth_headers(client)
        sid = client.post(
            "/session/start", json={"user_label": "mine"}, headers=owner
        ).json()["session_id"]
        client.post("/session/stop", headers=owner)

        stolen = client.delete(f"/session/{sid}", headers=attacker)
        assert stolen.status_code == 404, "a non-owner was able to delete this session"

        # The session must still exist and be deletable by its real owner.
        still_there = client.get("/session/summaries", headers=owner).json()
        assert any(s["session_id"] == sid for s in still_there)
        own_delete = client.delete(f"/session/{sid}", headers=owner)
        assert own_delete.status_code == 200


def test_export_rejects_a_different_user(service_app):
    """Same IDOR as above, for export: a non-owner must get the same 404 as a
    nonexistent session id, never the real owner's data."""
    with TestClient(service_app) as client:
        owner = auth_headers(client)
        attacker = auth_headers(client)
        sid = client.post(
            "/session/start", json={"user_label": "mine"}, headers=owner
        ).json()["session_id"]
        client.post("/session/stop", headers=owner)

        stolen = client.get(f"/session/{sid}/export", headers=attacker)
        assert stolen.status_code == 404, "a non-owner was able to export this session"

        own_export = client.get(f"/session/{sid}/export", headers=owner)
        assert own_export.status_code == 200


def test_calibration_get_and_clear(service_app):
    with TestClient(service_app) as client:
        h = auth_headers(client)
        # Not calibrated yet.
        assert client.get("/calibration", headers=h).json()["calibrated"] is False
        # Store, then read back.
        client.post(
            "/calibration",
            json={"hr_baseline": 70.0, "gsr_baseline": 60.0, "temp_baseline": 33.0},
            headers=h,
        )
        info = client.get("/calibration", headers=h).json()
        assert info["calibrated"] is True and info["hr_baseline"] == 70.0
        # Clear.
        assert client.delete("/calibration", headers=h).json() == {"status": "ok"}
        assert client.get("/calibration", headers=h).json()["calibrated"] is False


def test_export_all_returns_zip(service_app):
    with TestClient(service_app) as client:
        h = auth_headers(client)
        client.post("/session/start", json={"user_label": "z"}, headers=h)
        client.post("/session/stop", headers=h)
        resp = client.get("/session/export-all", headers=h)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        import io
        import zipfile

        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        assert len(zf.namelist()) == 1
        assert zf.namelist()[0].endswith(".json")


def test_export_all_requires_auth(service_app):
    with TestClient(service_app) as client:
        assert client.get("/session/export-all").status_code == 401


def test_session_list_scoped_to_user(service_app):
    with TestClient(service_app) as client:
        h1 = auth_headers(client)
        h2 = auth_headers(client)
        client.post("/session/start", json={"user_label": "mine"}, headers=h1)
        client.post("/session/stop", headers=h1)
        # User 2 sees none of user 1's sessions.
        assert client.get("/session/list", headers=h2).json() == []
        assert len(client.get("/session/list", headers=h1).json()) == 1
