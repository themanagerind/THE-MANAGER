"""
Auth request/response schemas.

Login flow (Section 2.1 identity model):
  1. POST /auth/otp/request  {mobile}                -> OTP sent
  2. POST /auth/otp/verify   {mobile, otp}            ->
       - if exactly one account matches this mobile -> tokens issued directly
       - if multiple accounts match (same mobile used across >1 society,
         or a society account + Platform Owner) -> AccountChoice[] returned,
         client must call /auth/select-account next
  3. POST /auth/select-account {mobile, otp_session_token, user_id} -> tokens
"""
import uuid

from pydantic import BaseModel

from app.models.enums import Role


class OTPRequestIn(BaseModel):
    mobile: str


class OTPRequestOut(BaseModel):
    message: str = "OTP sent"


class OTPVerifyIn(BaseModel):
    mobile: str
    otp: str


class AccountChoice(BaseModel):
    user_id: uuid.UUID
    society_id: uuid.UUID | None
    society_name: str | None
    full_name: str
    roles: list[Role]


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    active_role: Role
    available_roles: list[Role]


class OTPVerifyOut(BaseModel):
    """Either `tokens` is set (single unambiguous account) or `accounts` is
    set (caller must disambiguate via /auth/select-account) — never both."""

    tokens: TokenOut | None = None
    accounts: list[AccountChoice] | None = None
    otp_session_token: str | None = None  # short-lived, proves OTP already verified


class SelectAccountIn(BaseModel):
    otp_session_token: str
    user_id: uuid.UUID


class SwitchRoleIn(BaseModel):
    active_role: Role


class RefreshTokenIn(BaseModel):
    refresh_token: str
