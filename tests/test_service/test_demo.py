"""Demo-session endpoint test (public, no auth)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_demo_session_public_and_well_formed(service_app):
    with TestClient(service_app) as client:
        resp = client.get("/demo/session")  # no auth header
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "DEMO"
        assert body["duration_s"] == 180
        assert len(body["samples"]) == 180
        assert len(body["predictions"]) > 0
        assert {e["phase"] for e in body["events"]} == {
            "baseline", "stress", "breathing"
        }
        # Predictions carry the calibration flag added in 3.0.
        assert "calibration_applied" in body["predictions"][0]
        # The curated arc must actually contain a stress stretch.
        assert any(p["smoothed_label"] == "stress" for p in body["predictions"])


def test_demo_session_triggers_breathing_banner(service_app):
    """Guard the demo's centrepiece: the smoothed P(stress) must stay ≥0.7 for a
    continuous ≥30 s so the breathing auto-trigger banner fires during replay
    (matches the frontend useStressAlert rule: threshold 0.7, sustained 30 s).
    Protects against a future build_demo_session.py change silently flattening it.
    """
    THRESHOLD = 0.7
    SUSTAINED_MS = 30_000
    with TestClient(service_app) as client:
        preds = sorted(
            client.get("/demo/session").json()["predictions"],
            key=lambda p: p["timestamp_ms"],
        )

    def smoothed_p_stress(p: dict) -> float:
        # Mirror useStressAlert: smoothed_confidence is P(stress) when the
        # smoothed label is stress, else it's P(baseline).
        return (
            p["smoothed_confidence"]
            if p["smoothed_label"] == "stress"
            else 1 - p["smoothed_confidence"]
        )

    longest_ms = 0
    run_start = None
    for p in preds:
        if smoothed_p_stress(p) >= THRESHOLD:
            if run_start is None:
                run_start = p["timestamp_ms"]
            longest_ms = max(longest_ms, p["timestamp_ms"] - run_start)
        else:
            run_start = None

    assert longest_ms >= SUSTAINED_MS, (
        f"demo smoothed P(stress) sustained only {longest_ms} ms ≥{THRESHOLD}; "
        f"need ≥{SUSTAINED_MS} ms for the breathing banner to fire"
    )

    # Arc sanity: baseline start, a stress peak, and recovery back to baseline.
    assert preds[0]["smoothed_label"] == "baseline"
    assert preds[-1]["smoothed_label"] == "baseline"
