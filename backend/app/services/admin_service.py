"""
Admin self-signup service — an Admin signs up under an EXISTING, ACTIVE
society (created separately by the Platform Owner via their dashboard) and
waits for Platform Owner approval. Structurally mirrors
resident_service.signup_resident's hardening (rate limit, society
existence/ACTIVE check, clean duplicate-signup error) — same shape of
problem, different role and a different approver.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.models.enums import Role, SocietyStatus, UserStatus
from app.models.identity import Society, User, UserRole
from app.schemas.admin import AdminSignupIn

_SIGNUP_MAX_PER_HOUR = 5
_SIGNUP_RATE_WINDOW_SECONDS = 3600


def _signup_rate_key(mobile: str) -> str:
    return f"admin_signup:rate:{mobile}"


async def signup_admin(db: AsyncSession, body: AdminSignupIn) -> User:
    r = get_redis()
    attempts = await r.incr(_signup_rate_key(body.mobile))
    if attempts == 1:
        await r.expire(_signup_rate_key(body.mobile), _SIGNUP_RATE_WINDOW_SECONDS)
    if attempts > _SIGNUP_MAX_PER_HOUR:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many signup attempts — try again in an hour"
        )

    society = (await db.execute(select(Society).where(Society.id == body.society_id))).scalar_one_or_none()
    if society is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Society not found")
    if society.status != SocietyStatus.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "This society isn't accepting signups right now")

    admin = User(
        society_id=body.society_id,
        full_name=body.full_name,
        mobile=body.mobile,
        email=body.email,
        status=UserStatus.PENDING,
    )
    db.add(admin)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A signup already exists for this mobile number in this society"
        ) from exc

    db.add(
        UserRole(
            user_id=admin.id,
            role=Role.ADMIN,
            assigned_by=None,  # self-signup, not assigned by another user
            assigned_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    await db.refresh(admin)
    return admin


async def list_pending_admins(db: AsyncSession) -> list[User]:
    """Platform Owner sees pending Admin signups across every society —
    they're the approver regardless of which society an Admin is joining."""
    return (
        await db.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .where(
                User.status == UserStatus.PENDING,
                UserRole.role == Role.ADMIN,
                UserRole.revoked_at.is_(None),
            )
        )
    ).scalars().all()


async def decide_admin_approval(
    db: AsyncSession, admin_id: uuid.UUID, approve: bool, approved_by: uuid.UUID
) -> User:
    admin = (await db.execute(select(User).where(User.id == admin_id))).scalar_one_or_none()
    if admin is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Admin signup not found")
    if admin.status != UserStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Admin is already {admin.status.value}")

    admin.status = UserStatus.ACTIVE if approve else UserStatus.REJECTED
    admin.approved_by = approved_by
    admin.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(admin)
    return admin
