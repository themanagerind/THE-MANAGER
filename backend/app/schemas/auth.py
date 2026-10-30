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
<<<<<<< HEAD
    # Dev convenience only: SMS is mocked, so in development the OTP is
    # echoed here so login is completable without a real SMS gateway.
    # Never populated when environment != "development".
=======
    # Echoed only in development, or while SHOW_OTP_ON_SCREEN is on (a
    # temporary switch for before SMS delivery is fully active). Never
    # populated otherwise.
>>>>>>> 8ef6aa5dd8d08a8909e6d67aad9f9e88b0b9a641
    dev_otp: str | None = None


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


class CurrentUserOut(BaseModel):
    """GET /auth/me's response — deliberately NOT the same object as
    app.core.security.CurrentUser (audit finding): that internal DI type
    also carries access_jti/access_exp/session_started_at (the blocklist
    key and absolute-session-age bookkeeping), which have no business
    being handed to the client that already holds the token they're
    derived from — distinct from "can be decoded from the JWT anyway" in
    that there's still no reason to put them in a JSON response body
    clients/logs/XHR history will casually carry around."""

    user_id: uuid.UUID
    society_id: uuid.UUID | None
    active_role: Role
    available_roles: list[Role]


class SelectAccountIn(BaseModel):
    otp_session_token: str
    user_id: uuid.UUID


class SwitchRoleIn(BaseModel):
    active_role: Role
    # Required (audit finding) — auth_service.switch_role consumes this
    # exact refresh token's jti and issues a fresh one in the same step,
    # so the pre-switch token can never be left orphaned and un-revocable.
    refresh_token: str


class RefreshTokenIn(BaseModel):
    refresh_token: str
