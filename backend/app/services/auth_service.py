"""
Auth service — orchestrates the OTP verify -> (single account | choose
account) -> token issuance flow, and role switching.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    CurrentUser,
    create_access_token,
    create_otp_session_token,
    create_refresh_token,
    decode_otp_session_token,
)
from app.models.enums import Role, SocietyStatus, UserStatus
from app.models.identity import Society, User, UserRole
from app.schemas.auth import AccountChoice, OTPVerifyOut, TokenOut
from app.services import token_service


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


async def issue_tokens_for(db: AsyncSession, user: User) -> TokenOut:
    roles = await _active_roles_for(db, user.id)
    if not roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account has no active roles")
    active = _default_active_role(roles)
    jti = await token_service.issue_jti(user.id)
    return TokenOut(
        access_token=create_access_token(user.id, user.society_id, active, roles),
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


async def switch_role(db: AsyncSession, current: CurrentUser, new_role: Role) -> TokenOut:
    """Context/dashboard switch only — never creates a second account, never
    touches persistent role assignments (Section 4.3)."""
    if new_role not in current.available_roles:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, f"Role {new_role.value} not available for this account"
        )
    jti = await token_service.issue_jti(current.user_id)
    return TokenOut(
        access_token=create_access_token(
            current.user_id, current.society_id, new_role, current.available_roles
        ),
        refresh_token=create_refresh_token(current.user_id, jti),
        active_role=new_role,
        available_roles=current.available_roles,
    )


async def rotate_refresh_token(db: AsyncSession, user_id: uuid.UUID, old_jti: str) -> TokenOut:
    """Section: refresh-token rotation/revocation. Uses atomic GETDEL
    (fix, audit round-8 item 8) so two concurrent refresh calls with the
    same token can never both succeed — the second always sees it already
    consumed, closing the check-then-delete race window."""
    if not await token_service.consume_jti(user_id, old_jti):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Refresh token has been revoked or already used — please log in again",
        )

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or not active")
    if not await _society_is_active(db, user.society_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Society is suspended")
    return await issue_tokens_for(db, user)


async def logout(user_id: uuid.UUID, jti: str | None) -> None:
    if jti is not None:
        await token_service.revoke_jti(user_id, jti)
    else:
        await token_service.revoke_all_for_user(user_id)
