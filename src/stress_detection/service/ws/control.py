"""REST control endpoints - session lifecycle, labelling, export, calibration.

All endpoints are auth-protected (Depends(get_current_user)). Session start/stop
go through the Runtime (not the SessionManager directly) so per-user calibration
is loaded at session start and held for the session's lifetime.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response

from ..auth.dependencies import get_current_user
from ..auth.models import UserInfo
from .schemas import (
    CalibrationInfo,
    CalibrationRequest,
    CalibrationResponse,
    LabelRequest,
    SessionInfo,
    SessionSummary,
    StartSessionRequest,
    StartSessionResponse,
    StatusResponse,
    StopSessionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _runtime(request: Request):
    return request.app.state.runtime


def _session_mgr(request: Request):
    return request.app.state.runtime.session_mgr


@router.post("/session/start", response_model=StartSessionResponse)
async def start_session(
    body: StartSessionRequest,
    request: Request,
    user: UserInfo = Depends(get_current_user),
):
    """Begin recording a labelled session. Loads the user's calibration (if any
    and opted-in) for the session's lifetime. Returns session_id."""
    session_id = await _runtime(request).start_session(
        body.user_label, body.notes, user.user_id, body.use_calibration
    )
    return StartSessionResponse(session_id=session_id)


@router.post("/session/stop", response_model=StopSessionResponse)
async def stop_session(request: Request, user: UserInfo = Depends(get_current_user)):
    """End the current session."""
    session_id = await _runtime(request).stop_session()
    return StopSessionResponse(session_id=session_id)


@router.post("/session/label", response_model=StatusResponse)
async def label_session(
    body: LabelRequest, request: Request, user: UserInfo = Depends(get_current_user)
):
    """Attach a user-provided label to a timestamp. Targets body.session_id (a past
    session, from the History view) if given, else the active session."""
    ok = await _session_mgr(request).add_label(
        body.timestamp_ms, body.label, body.session_id
    )
    if not ok:
        raise HTTPException(
            status_code=409,
            detail="No session to annotate (none active and no session_id given).",
        )
    return StatusResponse(status="ok")


@router.get("/session/list", response_model=list[SessionInfo])
async def list_sessions(request: Request, user: UserInfo = Depends(get_current_user)):
    """List the current user's past sessions with metadata."""
    rows = await _session_mgr(request).list_sessions(user_id=user.user_id)
    return [SessionInfo(**row) for row in rows]


@router.get("/session/summaries", response_model=list[SessionSummary])
async def session_summaries(
    request: Request, user: UserInfo = Depends(get_current_user)
):
    """Per-session summaries (metadata + dominant state) for the History list.

    Computes the dominant smoothed state server-side in one query so the History
    view loads in a single round trip instead of fetching each session's full
    export. Declared BEFORE /session/{session_id}/export so "summaries" isn't
    captured as a session_id path param.
    """
    rows = await _session_mgr(request).session_summaries(user_id=user.user_id)
    return [SessionSummary(**row) for row in rows]


@router.get("/session/export-all")
async def export_all_sessions(
    request: Request, user: UserInfo = Depends(get_current_user)
):
    """Stream a ZIP of all the current user's session JSONs.

    Declared BEFORE /session/{session_id}/export so "export-all" isn't captured
    as a session_id path param.
    """
    data = await _session_mgr(request).export_all_zip(user_id=user.user_id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="sessions.zip"'},
    )


@router.get("/session/{session_id}/export")
async def export_session(
    session_id: str,
    request: Request,
    format: Literal["json", "csv"] = "json",
    user: UserInfo = Depends(get_current_user),
):
    """Download a past session's data + predictions.

    Scoped to the caller's own sessions: a session that exists but belongs to
    a different user returns the same 404 as one that doesn't exist at all,
    so this endpoint can't be used to enumerate other users' session ids.
    """
    try:
        path = await _session_mgr(request).export(session_id, format, user_id=user.user_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    media = "application/json" if format == "json" else "text/csv"
    return FileResponse(path, media_type=media, filename=path.name)


@router.delete("/session/{session_id}", response_model=StatusResponse)
async def delete_session(
    session_id: str, request: Request, user: UserInfo = Depends(get_current_user)
):
    """Delete a session and all its samples/predictions/labels.

    Scoped to the caller's own sessions - see export_session's docstring.
    """
    deleted = await _session_mgr(request).delete_session(session_id, user_id=user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    return StatusResponse(status="ok")


@router.post("/calibration", response_model=CalibrationResponse)
async def set_calibration(
    body: CalibrationRequest,
    request: Request,
    user: UserInfo = Depends(get_current_user),
):
    """Store the authenticated user's resting baseline.

    Applied during inference for sessions started with use_calibration=True (see
    Runtime.start_session). This is a heuristic personalisation, not formally
    validated domain adaptation - see CalibrationOffsets docstring.
    """
    payload = {
        "gsr_baseline": body.gsr_baseline,
        "hr_baseline": body.hr_baseline,
        "temp_baseline": body.temp_baseline,
        "extra": body.extra,
    }
    await _session_mgr(request).set_calibration(user.user_id, payload)
    return CalibrationResponse(status="ok", user_id=user.user_id)


@router.get("/calibration", response_model=CalibrationInfo)
async def get_calibration(request: Request, user: UserInfo = Depends(get_current_user)):
    """Return the authenticated user's current calibration (or calibrated=False)."""
    row = await _session_mgr(request).get_calibration(user.user_id)
    if row is None:
        return CalibrationInfo(calibrated=False, user_id=user.user_id)
    return CalibrationInfo(
        calibrated=True,
        user_id=user.user_id,
        gsr_baseline=row.get("gsr_baseline"),
        hr_baseline=row.get("hr_baseline"),
        temp_baseline=row.get("temp_baseline"),
        captured_at_ms=row.get("captured_at_ms"),
    )


@router.delete("/calibration", response_model=StatusResponse)
async def clear_calibration(
    request: Request, user: UserInfo = Depends(get_current_user)
):
    """Clear the authenticated user's calibration."""
    await _session_mgr(request).clear_calibration(user.user_id)
    return StatusResponse(status="ok")
