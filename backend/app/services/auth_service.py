"""
Auth service — orchestrates the OTP verify -> (single account | choose
account) -> token issuance flow, and role switching.
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    CurrentUser,
    create_access_token,
    create_otp_session_token,
    create_refresh_token,
    decode_otp_session_token,
    decode_token,
    revoke_access_token,
)
from app.models.enums import Role, SocietyStatus, UserStatus
from app.models.identity import Society, User, UserRole
from app.schemas.auth import AccountChoice, OTPVerifyOut, TokenOut
from app.services import token_service

# User-requested: the 12-hour absolute session cap applies to Platform
# Owner only for now — Admin and Sub-admin were disabled from this set
# (were both included briefly; see git history) pending further
# discussion, so a 12h-old Admin/Sub-admin session still refreshes freely
# like Manager/Guard/Resident. Only Platform Owner is capped below.
_PRIVILEGED_ROLES = {Role.PLATFORM_OWNER}
_PRIVILEGED_SESSION_CAP = timedelta(hours=12)


async def _society_is_active(db: AsyncSession, society_id: uuid.UUID | None) -> bool:
    if society_id is None:
        return True  # Platform Owner rows have no society
    society = (
        await db.execute(select(Society).where(Society.id == society_id))
    ).scalar_one_or_none()
    return society is not None and society.status == SocietyStatus.ACTIVE


async def _active_roles_for(db: AsyncSession, user_id: uuid.UUID) -> list[Role]:
    rows = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.revoked_at.is_(None))
        )
    ).scalars().all()
    return [Role(r.role) for r in rows]


def _default_active_role(roles: list[Role]) -> Role:
    # Pick a sensible default landing mode; RESIDENT last so an Admin/Sub-admin
    # lands in their management dashboard by default, not Resident mode.
    priority = [
        Role.PLATFORM_OWNER, Role.ADMIN, Role.SUB_ADMIN,
        Role.MANAGER, Role.SECURITY_GUARD, Role.RESIDENT,
    ]
    for p in priority:
        if p in roles:
            return p
    raise HTTPException(status.HTTP_403_FORBIDDEN, "User has no active roles")


async def issue_tokens_for(
    db: AsyncSession, user: User, session_started_at: datetime | None = None
) -> TokenOut:
    """`session_started_at` left as None means a fresh login — the session
    clock starts now. A caller carrying forward an existing session
    (rotate_refresh_token) passes the original value through instead, so
    the 12-hour privileged-role cap measures from the real login."""
    roles = await _active_roles_for(db, user.id)
    if not roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account has no active roles")
    active = _default_active_role(roles)
    started = session_started_at or datetime.now(timezone.utc)
    jti = await token_service.issue_jti(user.id, started)
    return TokenOut(
        access_token=create_access_token(user.id, user.society_id, active, roles, started),
        refresh_token=create_refresh_token(user.id, jti),
        active_role=active,
        available_roles=roles,
    )


async def resolve_login(db: AsyncSession, mobile: str) -> OTPVerifyOut:
    """Called after OTP is verified. Finds every ACTIVE user row for this
    mobile (Section 2.1: may be >1 across societies + Platform Owner) and
    either issues tokens directly or returns a disambiguation list."""
    users = (
        await db.execute(
            select(User)
            .outerjoin(Society, User.society_id == Society.id)
            .where(
                User.mobile == mobile,
                User.status == UserStatus.ACTIVE,
                or_(User.society_id.is_(None), Society.status == SocietyStatus.ACTIVE),
            )
        )
    ).scalars().all()

    if not users:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active account for this mobile")

    if len(users) == 1:
        tokens = await issue_tokens_for(db, users[0])
        return OTPVerifyOut(tokens=tokens)

    # Multiple accounts — disambiguate (Section 2.1: no shared cross-society
    # identity, so this mobile legitimately belongs to >1 separate user row).
    choices: list[AccountChoice] = []
    for u in users:
        society_name = None
        if u.society_id:
            soc = (
                await db.execute(select(Society).where(Society.id == u.society_id))
            ).scalar_one_or_none()
            society_name = soc.name if soc else None
        roles = await _active_roles_for(db, u.id)
        choices.append(
            AccountChoice(
                user_id=u.id, society_id=u.society_id, society_name=society_name,
                full_name=u.full_name, roles=roles,
            )
        )
    return OTPVerifyOut(accounts=choices, otp_session_token=create_otp_session_token(mobile))


async def select_account(db: AsyncSession, otp_session_token: str, user_id: uuid.UUID) -> TokenOut:
    mobile = decode_otp_session_token(otp_session_token)
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or user.mobile != mobile or user.status != UserStatus.ACTIVE:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid account selection")
    if not await _society_is_active(db, user.society_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Society is suspended")
    return await issue_tokens_for(db, user)


async def switch_role(
    db: AsyncSession, current: CurrentUser, new_role: Role, refresh_token: str
) -> TokenOut:
    """Context/dashboard switch only — never creates a second account, never
    touches persistent role assignments (Section 4.3).

    Consumes the caller's current refresh token and issues a fresh one —
    audit finding: this used to mint a brand-new jti without revoking the
    old one, so every role switch forked off a permanently orphaned,
    still-valid (up to 30 days) refresh token that /auth/logout could
    never reach (it only revokes the ONE jti the client currently holds).
    Anyone holding an earlier such token — e.g. via a leaked pre-switch
    token — could mint fresh sessions for the account indefinitely,
    bypassing both logout and the access-token blocklist. Now behaves
    exactly like rotate_refresh_token (atomic consume via GETDEL, same
    12-hour privileged-role cap check, session_started_at carried forward
    unchanged so a switch never resets the clock), just also changing
    active_role in the same step."""
    if new_role not in current.available_roles:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, f"Role {new_role.value} not available for this account"
        )

    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not a refresh token")
    if uuid.UUID(payload["sub"]) != current.user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token does not belong to this account")
    old_jti = payload.get("jti")
    if old_jti is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed refresh token")

    session_started_at = await token_service.consume_jti(current.user_id, old_jti)
    if session_started_at is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Refresh token has been revoked or already used — please log in again",
        )

    if any(r in _PRIVILEGED_ROLES for r in current.available_roles):
        if datetime.now(timezone.utc) - session_started_at > _PRIVILEGED_SESSION_CAP:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Session expired after 12 hours for this account type — please log in again",
            )

    jti = await token_service.issue_jti(current.user_id, session_started_at)
    return TokenOut(
        access_token=create_access_token(
            current.user_id, current.society_id, new_role, current.available_roles,
            session_started_at,
        ),
        refresh_token=create_refresh_token(current.user_id, jti),
        active_role=new_role,
        available_roles=current.available_roles,
    )


async def rotate_refresh_token(db: AsyncSession, user_id: uuid.UUID, old_jti: str) -> TokenOut:
    """Section: refresh-token rotation/revocation. Uses atomic GETDEL
    (fix, audit round-8 item 8) so two concurrent refresh calls with the
    same token can never both succeed — the second always sees it already
    consumed, closing the check-then-delete race window.

    consume_jti's return value is the session's original login time, which
    this both uses to enforce the 12-hour absolute cap for privileged
    roles (checked fresh against current DB roles, not whatever role the
    stale token last claimed) and carries forward unchanged into the new
    token pair — a refresh must never reset the session clock."""
    session_started_at = await token_service.consume_jti(user_id, old_jti)
    if session_started_at is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Refresh token has been revoked or already used — please log in again",
        )

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or not active")
    if not await _society_is_active(db, user.society_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Society is suspended")

    roles = await _active_roles_for(db, user_id)
    if any(r in _PRIVILEGED_ROLES for r in roles):
        if datetime.now(timezone.utc) - session_started_at > _PRIVILEGED_SESSION_CAP:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Session expired after 12 hours for this account type — please log in again",
            )

    return await issue_tokens_for(db, user, session_started_at=session_started_at)


async def logout(
    user_id: uuid.UUID, refresh_jti: str | None, access_jti: str, access_exp: datetime
) -> None:
    """Revokes the refresh token (as before) AND blocklists the access
    token that authenticated this very logout call for its remaining
    lifetime (user-reported gap: previously an already-issued access
    token stayed usable for up to ~30 more minutes after logout, since
    only the refresh token was revoked and a JWT can't be individually
    recalled by signature alone)."""
    if refresh_jti is not None:
        await token_service.revoke_jti(user_id, refresh_jti)
    else:
        await token_service.revoke_all_for_user(user_id)
    ttl_seconds = int((access_exp - datetime.now(timezone.utc)).total_seconds())
    await revoke_access_token(access_jti, ttl_seconds)
