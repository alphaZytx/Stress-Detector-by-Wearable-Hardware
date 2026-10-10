"""Request/response schemas for the REST control endpoints.

Small and explicit - no catch-all "any" types on the wire. The frontend (Phase 3)
consumes these directly, so keep them stable.
"""

from __future__ import annotations

from pydantic import BaseModel


class StartSessionRequest(BaseModel):
    user_label: str | None = None
    notes: str | None = None
    # Opt out of applying this user's calibration for this session.
    use_calibration: bool = True


class StartSessionResponse(BaseModel):
    session_id: str


class StopSessionResponse(BaseModel):
    session_id: str | None


class LabelRequest(BaseModel):
    timestamp_ms: int
    label: str
    # Target a specific (possibly past) session. If omitted, the active session
    # is used. The History view sets this to annotate a finished session.
    session_id: str | None = None


class StatusResponse(BaseModel):
    status: str


class SessionInfo(BaseModel):
    session_id: str
    started_at_ms: int
    ended_at_ms: int | None = None
    user_label: str | None = None
    notes: str | None = None
    user_id: str | None = None


class SessionSummary(BaseModel):
    """Lightweight History-list row: metadata + server-computed dominant state.

    Lets the History view render the per-session stress badge without fetching
    each session's full export (avoids the N+1 round trip).
    """

    session_id: str
    started_at_ms: int
    ended_at_ms: int | None = None
    user_label: str | None = None
    notes: str | None = None
    dominant_state: str | None = None  # "baseline" | "stress" | None (no predictions)
    dominant_state_pct: float = 0.0


class CalibrationRequest(BaseModel):
    # user_id is optional on the wire: the authenticated user always wins, so the
    # frontend need not (and should not) send it. Kept for back-compat.
    user_id: str | None = None
    gsr_baseline: float | None = None
    hr_baseline: float | None = None
    temp_baseline: float | None = None
    # Optional free-form extra fields the frontend may capture during calibration.
    extra: dict = {}


class CalibrationResponse(BaseModel):
    status: str
    user_id: str


class CalibrationInfo(BaseModel):
    """Current calibration for a user, or calibrated=False if none stored."""

    calibrated: bool
    user_id: str
    gsr_baseline: float | None = None
    hr_baseline: float | None = None
    temp_baseline: float | None = None
    captured_at_ms: int | None = None
