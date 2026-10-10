"""FastAPI auth dependencies.

``get_current_user`` validates the ``Authorization: Bearer <jwt>`` header and
returns the ``UserInfo``. Raises 401 on a missing, malformed, expired, or
unknown-user token.

``authenticate_token`` is the shared core (also used by the WebSocket route,
which passes the token via a query parameter rather than a header).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import UserDb
from .jwt_utils import TokenError, decode_token
from .models import UserInfo

# auto_error=False so we can raise a 401 (not HTTPBearer's default 403) ourselves.
_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def _user_db(request: Request) -> UserDb:
    return request.app.state.user_db


async def authenticate_token(token: str, user_db: UserDb) -> UserInfo:
    """Decode a raw token string and resolve it to a UserInfo, or raise 401."""
    try:
        payload = decode_token(token)
    except TokenError:
        raise _UNAUTHORIZED
    user_id = payload.get("sub")
    if not user_id:
        raise _UNAUTHORIZED
    row = await user_db.get_by_id(user_id)
    if row is None:
        raise _UNAUTHORIZED
    return UserInfo(
        user_id=row["user_id"],
        email=row["email"],
        display_name=row["display_name"],
        created_at_ms=row["created_at_ms"],
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserInfo:
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED
    return await authenticate_token(credentials.credentials, _user_db(request))
