"""Auth endpoints — Section 2.1 login flow + Section 4.3 role switching."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import (
    CurrentUser,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from app.models.identity import User
from app.schemas.auth import (
    CurrentUserOut,
    OTPRequestIn,
    OTPRequestOut,
    OTPVerifyIn,
    OTPVerifyOut,
    RefreshTokenIn,
    SelectAccountIn,
    SwitchRoleIn,
    TokenOut,
)
from app.services import auth_service
from app.services.otp_service import request_otp, verify_otp
from app.services.sms_service import send_otp_sms

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/otp/request", response_model=OTPRequestOut)
async def request_otp_endpoint(body: OTPRequestIn) -> OTPRequestOut:
    otp = await request_otp(body.mobile)
    # Sends via Twilio when configured, otherwise logs (see sms_service).
    await send_otp_sms(body.mobile, otp)
    # Echo the OTP so login works without a working SMS gateway: always in
    # development, and in other environments only while the temporary
    # SHOW_OTP_ON_SCREEN flag is on (see Settings.show_otp_on_screen).
    if settings.environment == "development" or settings.show_otp_on_screen:
        return OTPRequestOut(dev_otp=otp)
    return OTPRequestOut()


@router.post("/otp/verify", response_model=OTPVerifyOut)
async def verify_otp_endpoint(
    body: OTPVerifyIn, db: Annotated[AsyncSession, Depends(get_db)]
) -> OTPVerifyOut:
    if not await verify_otp(body.mobile, body.otp):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired OTP")
    return await auth_service.resolve_login(db, body.mobile)


@router.post("/select-account", response_model=TokenOut)
async def select_account_endpoint(
    body: SelectAccountIn, db: Annotated[AsyncSession, Depends(get_db)]
) -> TokenOut:
    return await auth_service.select_account(db, body.otp_session_token, body.user_id)


@router.post("/switch-role", response_model=TokenOut)
async def switch_role_endpoint(
    body: SwitchRoleIn,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenOut:
    return await auth_service.switch_role(db, current, body.active_role, body.refresh_token)


@router.post("/token/refresh", response_model=TokenOut)
async def refresh_token_endpoint(
    body: RefreshTokenIn, db: Annotated[AsyncSession, Depends(get_db)]
) -> TokenOut:
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not a refresh token")

    user_id = uuid.UUID(payload["sub"])
    jti = payload.get("jti")
    if jti is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed refresh token")
    return await auth_service.rotate_refresh_token(db, user_id, jti)


@router.post("/logout")
async def logout_endpoint(
    body: RefreshTokenIn, current: Annotated[CurrentUser, Depends(get_current_user)]
) -> dict:
    """Revokes the refresh token tied to the current session, AND
    blocklists the access token used to authenticate this call for its
    remaining lifetime (current.access_jti/access_exp) — see
    auth_service.logout. Pass refresh_token so its specific jti is
    invalidated (not every session)."""
    payload = decode_token(body.refresh_token)
    jti = payload.get("jti")
    await auth_service.logout(current.user_id, jti, current.access_jti, current.access_exp)
    return {"message": "Logged out"}


@router.get("/me", response_model=CurrentUserOut)
async def get_me(current: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUserOut:
    # Deliberately NOT `return current` (audit finding) — CurrentUser also
    # carries access_jti/access_exp/session_started_at, which have no
    # business in a JSON response body. CurrentUserOut is the public shape.
    return CurrentUserOut(
        user_id=current.user_id,
        society_id=current.society_id,
        active_role=current.active_role,
        available_roles=current.available_roles,
    )
