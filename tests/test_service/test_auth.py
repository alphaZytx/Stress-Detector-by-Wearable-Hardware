"""Auth tests: register, login, me, logout, invalid token, expired token."""

from __future__ import annotations

import time
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

from stress_detection.service.auth import jwt_utils
from stress_detection.service.auth.passwords import hash_password, verify_password


def _email() -> str:
    return f"u-{uuid.uuid4().hex[:8]}@example.com"


def test_password_hash_roundtrip():
    h = hash_password("correct horse")
    assert h != "correct horse"
    assert verify_password("correct horse", h)
    assert not verify_password("wrong", h)


def test_password_over_72_bytes_does_not_raise():
    long_pw = "a" * 200
    h = hash_password(long_pw)
    assert verify_password(long_pw, h)


def test_register_returns_token_and_user(service_app):
    with TestClient(service_app) as client:
        email = _email()
        resp = client.post(
            "/auth/register",
            json={"email": email, "password": "secret123", "display_name": "Ada"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["user"]["email"] == email
        assert body["user"]["display_name"] == "Ada"


def test_register_duplicate_email_409(service_app):
    with TestClient(service_app) as client:
        email = _email()
        payload = {"email": email, "password": "secret123"}
        assert client.post("/auth/register", json=payload).status_code == 200
        assert client.post("/auth/register", json=payload).status_code == 409


def test_login_success_and_failure(service_app):
    with TestClient(service_app) as client:
        email = _email()
        client.post("/auth/register", json={"email": email, "password": "secret123"})

        ok = client.post("/auth/login", json={"email": email, "password": "secret123"})
        assert ok.status_code == 200
        assert ok.json()["access_token"]

        bad = client.post("/auth/login", json={"email": email, "password": "nope"})
        assert bad.status_code == 401

        missing = client.post(
            "/auth/login", json={"email": _email(), "password": "secret123"}
        )
        assert missing.status_code == 401


def test_me_returns_current_user(service_app):
    with TestClient(service_app) as client:
        email = _email()
        token = client.post(
            "/auth/register", json={"email": email, "password": "secret123"}
        ).json()["access_token"]
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == email


def test_me_without_token_401(service_app):
    with TestClient(service_app) as client:
        assert client.get("/auth/me").status_code == 401


def test_me_with_garbage_token_401(service_app):
    with TestClient(service_app) as client:
        resp = client.get(
            "/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"}
        )
        assert resp.status_code == 401


def test_logout_ok(service_app):
    with TestClient(service_app) as client:
        token = client.post(
            "/auth/register", json={"email": _email(), "password": "secret123"}
        ).json()["access_token"]
        resp = client.post(
            "/auth/logout", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_expired_token_rejected(service_app):
    """A token whose exp is in the past must be rejected at decode and at /me."""
    secret = jwt_utils._secret()
    past = int(time.time()) - 10
    expired = jwt.encode(
        {"sub": "x", "email": "x@x.com", "iat": past - 100, "exp": past},
        secret,
        algorithm="HS256",
    )
    with pytest.raises(jwt_utils.TokenError):
        jwt_utils.decode_token(expired)

    with TestClient(service_app) as client:
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {expired}"}
        )
        assert resp.status_code == 401


def test_create_token_roundtrip():
    token, exp_ms = jwt_utils.create_token("user-1", "user@example.com")
    payload = jwt_utils.decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["email"] == "user@example.com"
    assert exp_ms > int(time.time() * 1000)
