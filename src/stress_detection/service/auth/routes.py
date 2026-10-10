"""Auth REST router: register / login / me / logout."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from .db import EmailTakenError, UserDb
from .dependencies import get_current_user
from .jwt_utils import create_token
from .models import TokenResponse, UserCreate, UserInfo, UserLogin
from .passwords import hash_password, verify_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_db(request: Request) -> UserDb:
    return request.app.state.user_db


def _token_response(user: dict) -> TokenResponse:
    token, expires_at_ms = create_token(user["user_id"], user["email"])
    return TokenResponse(
        access_token=token,
        expires_at_ms=expires_at_ms,
        user=UserInfo(
            user_id=user["user_id"],
            email=user["email"],
            display_name=user.get("display_name"),
            created_at_ms=user["created_at_ms"],
        ),
    )


@router.post("/register", response_model=TokenResponse)
async def register(body: UserCreate, request: Request) -> TokenResponse:
    db = _user_db(request)
    try:
        user = await db.create_user(
            email=body.email,
            password_hash=hash_password(body.password),
            display_name=body.display_name,
        )
    except EmailTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, request: Request) -> TokenResponse:
    db = _user_db(request)
    user = await db.get_by_email(body.email)
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    return _token_response(user)


@router.get("/me", response_model=UserInfo)
async def me(current: UserInfo = Depends(get_current_user)) -> UserInfo:
    return current


@router.post("/logout")
async def logout(current: UserInfo = Depends(get_current_user)) -> dict:
    # Stateless JWT - nothing to revoke server-side. The frontend drops the token.
    # Endpoint exists so the contract is symmetric and so logout is auth-gated.
    return {"status": "ok"}
