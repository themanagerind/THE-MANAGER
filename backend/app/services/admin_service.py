"""
Admin self-signup service — an Admin signs up under an EXISTING, ACTIVE
society (created separately by the Platform Owner via their dashboard) and
waits for Platform Owner approval. Structurally mirrors
resident_service.signup_resident's hardening (rate limit, society
existence/ACTIVE check, clean duplicate-signup error) — same shape of
problem, different role and a different approver.
"""
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.models.enums import RelationshipType, Role, SocietyStatus, UserStatus
from app.models.identity import Property, PropertyResident, Society, User, UserRole
from app.schemas.admin import AdminSignupIn
from app.services.resident_service import has_active_owner

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

    # Mandatory dual-role link (Section 4: every Admin is ADMIN+RESIDENT)
    # — same picker/invariant as resident_service.signup_resident, for a
    # unit the Platform Owner has already mapped. Checked before creating
    # the User row so a doomed signup never gets that far.
    prop = (
        await db.execute(
            select(Property).where(
                Property.id == body.existing_property_id, Property.society_id == body.society_id
            )
        )
    ).scalar_one_or_none()
    if prop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Property not found in this society")
    if body.existing_property_relationship == RelationshipType.TENANT and not await has_active_owner(
        db, body.existing_property_id
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This property has no active Owner yet — a Tenant signup needs an Owner on record "
            "first (Section 12 invariant).",
        )

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

    # Mandatory dual-role link (Section 4: ADMIN+RESIDENT) — stays
    # uncommitted (db.add only) until the single db.commit() below,
    # alongside the admin User/ADMIN role added above, so nothing is
    # reachable either way until Platform Owner approval activates the
    # account (decide_admin_approval below).
    db.add(
        UserRole(
            user_id=admin.id, role=Role.RESIDENT, assigned_by=None,
            assigned_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        PropertyResident(
            society_id=body.society_id, property_id=prop.id, resident_id=admin.id,
            relationship_type=body.existing_property_relationship, is_active=True,
            start_date=date.today(), created_at=datetime.now(timezone.utc),
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
