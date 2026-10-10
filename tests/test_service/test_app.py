from fastapi import FastAPI
from fastapi.testclient import TestClient

from stress_detection.service.app import create_app
from stress_detection.service.config import get_service_config

from .conftest import auth_headers


def test_create_app_returns_fastapi():
    app = create_app()
    assert isinstance(app, FastAPI)
    assert app.title == "Stress Detection Service"


def test_health_endpoint():
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_config_requires_auth(service_app):
    with TestClient(service_app) as client:
        resp = client.get("/config")
        assert resp.status_code == 401


def test_config_endpoint(service_app):
    with TestClient(service_app) as client:
        resp = client.get("/config", headers=auth_headers(client))
        assert resp.status_code == 200
        body = resp.json()
        # Top-level config sections present
        for key in ("service", "input", "inference", "session"):
            assert key in body, f"missing config section: {key}"
        # Derived windowing fields surfaced for the streamer
        assert body["window_s"] == 30
        assert body["stride_s"] == 5
        # Paths serialised as strings, not Path objects
        assert isinstance(body["inference"]["model_path"], str)


def test_config_matches_singleton():
    cfg = get_service_config()
    assert cfg.input.source in ("synthetic", "csv_replay", "serial", "tcp")
    assert cfg.window_s == 30
    assert cfg.stride_s == 5
