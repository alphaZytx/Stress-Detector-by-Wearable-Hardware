"""WebSocket route - clients connect here to receive the live stream.

Auth: browsers can't set headers on the WebSocket constructor, so the JWT is
passed as a ``?token=`` query parameter. An invalid/missing token is rejected
with close code 4401 (application-defined "unauthorized") before the stream
starts.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from ..auth.dependencies import authenticate_token

logger = logging.getLogger(__name__)

router = APIRouter()

WS_UNAUTHORIZED_CODE = 4401


@router.websocket("/ws/stream")
async def stream(ws: WebSocket, token: str | None = Query(default=None)) -> None:
    # Validate before accepting the stream. We accept first (handshake) then
    # close with 4401 so the client receives a clean application close code.
    await ws.accept()
    if not token:
        await ws.close(code=WS_UNAUTHORIZED_CODE, reason="missing token")
        return
    try:
        await authenticate_token(token, ws.app.state.user_db)
    except Exception:  # noqa: BLE001 - any auth failure (TokenError/HTTP 401) → 4401
        await ws.close(code=WS_UNAUTHORIZED_CODE, reason="invalid token")
        return

    broadcaster = ws.app.state.runtime.broadcaster
    await broadcaster.add_client(ws)
    try:
        while True:
            # We don't expect client messages on this socket; just keep it open
            # so we notice disconnects.
            await ws.receive_text()
    except WebSocketDisconnect:
        await broadcaster.remove_client(ws)
