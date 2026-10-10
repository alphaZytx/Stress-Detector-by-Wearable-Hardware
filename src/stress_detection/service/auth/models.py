"""Pydantic models for the auth wire contract."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    display_name: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserInfo(BaseModel):
    user_id: str
    email: str
    display_name: str | None = None
    created_at_ms: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at_ms: int
    user: UserInfo
