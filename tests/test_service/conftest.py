"""Shared fixtures/helpers for service tests.

Auth (3.0) protects /config, /session/*, /calibration, and /ws/stream, so tests
that hit those endpoints need a token. These helpers also point the app at a
temp SQLite file so tests don't pollute (or collide on) the real data/ DB.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from stress_detection.service.app import create_app
from stress_detection.service.config import get_service_config


@pytest.fixture
def service_cfg(tmp_path):
    """Service config pointed at a temp DB, replaying CSV fast for quick streams."""
    cfg = get_service_config()
    cfg.input.source = "csv_replay"
    cfg.input.csv_replay.speed = 50.0
    cfg.input.csv_replay.loop = True
    cfg.session.db_path = tmp_path / "sessions.sqlite"
    cfg.session.export_dir = tmp_path / "export"
    return cfg


@pytest.fixture
def service_app(service_cfg):
    return create_app(service_cfg)


def register_and_token(client: TestClient, email: str | None = None) -> str:
    """Register a fresh user and return their bearer token."""
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "hunter2pw", "display_name": "Test"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_headers(client: TestClient, email: str | None = None) -> dict:
    return {"Authorization": f"Bearer {register_and_token(client, email)}"}
