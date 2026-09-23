"""
Resident service — Section 9 (Resident), Section 12 (Property Occupancy),
Section 26 (Resident approval flow).

Key invariant enforced here (Schema Spec v1.3 `property_residents` note —
a trigger/service rule, not a plain CHECK since it's cross-row):
  An active TENANT relationship requires at least one active OWNER
  relationship on the same property, both when creating a tenant link and
  when deactivating an owner link.
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
from app.schemas.resident import AdminSelfResidentLinkIn, PropertyResidentLinkIn, ResidentSignupIn

_SIGNUP_MAX_PER_HOUR = 5
_SIGNUP_RATE_WINDOW_SECONDS = 3600


def _signup_rate_key(mobile: str) -> str:
    return f"resident_signup:rate:{mobile}"


async def signup_resident(db: AsyncSession, body: ResidentSignupIn) -> User:
    # Audit fix: public, unauthenticated endpoint had no rate limiting at
    # all — same pattern as otp_service's request rate limit, keyed by
    # mobile so it can't be trivially bypassed by varying society_id.
    r = get_redis()
    attempts = await r.incr(_signup_rate_key(body.mobile))
    if attempts == 1:
        await r.expire(_signup_rate_key(body.mobile), _SIGNUP_RATE_WINDOW_SECONDS)
    if attempts > _SIGNUP_MAX_PER_HOUR:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many signup attempts — try again in an hour"
        )

    # Audit fix: society_id was trusted blindly — a nonexistent society_id
    # surfaced as a raw FK-violation 500, and a real but PENDING/SUSPENDED
    # society had no gate at all (self-signup into a society that hasn't
    # even been approved yet, or has been suspended).
    society = (await db.execute(select(Society).where(Society.id == body.society_id))).scalar_one_or_none()
    if society is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Society not found")
    if society.status != SocietyStatus.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "This society isn't accepting signups right now")

    resident = User(
        society_id=body.society_id,
        full_name=body.full_name,
        mobile=body.mobile,
        email=body.email,
        status=UserStatus.PENDING,
    )
    db.add(resident)
    try:
        await db.flush()
    except IntegrityError as exc:
        # Audit fix: a duplicate (society_id, mobile) signup previously
        # bubbled up as an unhandled 500 instead of a clean error — the DB
        # unique index (ux_users_society_mobile) is what actually blocks it.
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A signup already exists for this mobile number in this society"
        ) from exc

    db.add(
        UserRole(
            user_id=resident.id,
            role=Role.RESIDENT,
            assigned_by=None,
            assigned_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    await db.refresh(resident)
    return resident


async def list_pending_residents(db: AsyncSession, society_id: uuid.UUID) -> list[User]:
    return (
        await db.execute(
            select(User).where(User.society_id == society_id, User.status == UserStatus.PENDING)
        )
    ).scalars().all()


async def decide_resident_approval(
    db: AsyncSession,
    society_id: uuid.UUID,
    resident_id: uuid.UUID,
    approve: bool,
    approved_by: uuid.UUID,
) -> User:
    resident = (
        await db.execute(
            select(User).where(User.id == resident_id, User.society_id == society_id)
        )
    ).scalar_one_or_none()
    if resident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resident not found in this society")
    if resident.status != UserStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Resident is already {resident.status.value}")

    resident.status = UserStatus.ACTIVE if approve else UserStatus.REJECTED
    resident.approved_by = approved_by
    resident.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(resident)
    return resident


async def has_active_owner(db: AsyncSession, property_id: uuid.UUID) -> bool:
    row = (
        await db.execute(
            select(PropertyResident).where(
                PropertyResident.property_id == property_id,
                PropertyResident.relationship_type == RelationshipType.OWNER,
                PropertyResident.is_active.is_(True),
            )
        )
    ).first()
    return row is not None


async def link_resident_to_property(
    db: AsyncSession, society_id: uuid.UUID, body: PropertyResidentLinkIn
) -> PropertyResident:
    prop = (
        await db.execute(
            select(Property).where(Property.id == body.property_id, Property.society_id == society_id)
        )
    ).scalar_one_or_none()
    if prop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Property not found in this society")

    resident = (
        await db.execute(
            select(User).where(
                User.id == body.resident_id, User.society_id == society_id, User.status == UserStatus.ACTIVE
            )
        )
    ).scalar_one_or_none()
    if resident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Active resident not found in this society")

    if body.relationship_type == RelationshipType.TENANT and not await has_active_owner(
        db, body.property_id
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot add an active Tenant: property has no active Owner (Section 12 invariant)",
        )

    link = PropertyResident(
        society_id=society_id,
        property_id=body.property_id,
        resident_id=body.resident_id,
        relationship_type=body.relationship_type,
        is_active=True,
        start_date=body.start_date or date.today(),
        created_at=datetime.now(timezone.utc),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def link_admin_as_resident(
    db: AsyncSession, society_id: uuid.UUID, admin_user_id: uuid.UUID, body: AdminSelfResidentLinkIn
) -> PropertyResident:
    """Admin links themselves to a property in their own society (Section
    4's dual-role model, e.g. an Admin who also owns a flat there). Grants
    a RESIDENT role on their existing account if they don't already have
    one — never a new User row, unlike the public Resident signup form —
    so the same account can switch between Admin and Resident dashboards
    (RoleSwitcher) right after this call."""
    prop = (
        await db.execute(
            select(Property).where(Property.id == body.property_id, Property.society_id == society_id)
        )
    ).scalar_one_or_none()
    if prop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Property not found in this society")

    if body.relationship_type == RelationshipType.TENANT and not await has_active_owner(
        db, body.property_id
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot add an active Tenant: property has no active Owner (Section 12 invariant)",
        )

    existing_resident_role = (
        await db.execute(
            select(UserRole).where(
                UserRole.user_id == admin_user_id,
                UserRole.role == Role.RESIDENT,
                UserRole.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing_resident_role is None:
        db.add(
            UserRole(
                user_id=admin_user_id,
                role=Role.RESIDENT,
                assigned_by=admin_user_id,
                assigned_at=datetime.now(timezone.utc),
            )
        )

    link = PropertyResident(
        society_id=society_id,
        property_id=body.property_id,
        resident_id=admin_user_id,
        relationship_type=body.relationship_type,
        is_active=True,
        start_date=date.today(),
        created_at=datetime.now(timezone.utc),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def unlink_resident_from_property(
    db: AsyncSession, society_id: uuid.UUID, link_id: uuid.UUID
) -> PropertyResident:
    """Deactivates a property_residents row (never hard-deletes — Section 12).
    Blocks deactivating the last active Owner while an active Tenant remains,
    preserving the same invariant in the other direction."""
    link = (
        await db.execute(
            select(PropertyResident).where(
                PropertyResident.id == link_id, PropertyResident.society_id == society_id
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found in this society")
    if not link.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Link is already inactive")

    if link.relationship_type == RelationshipType.OWNER:
        other_active_owner = (
            await db.execute(
                select(PropertyResident).where(
                    PropertyResident.property_id == link.property_id,
                    PropertyResident.relationship_type == RelationshipType.OWNER,
                    PropertyResident.is_active.is_(True),
                    PropertyResident.id != link.id,
                )
            )
        ).first()
        active_tenant_exists = (
            await db.execute(
                select(PropertyResident).where(
                    PropertyResident.property_id == link.property_id,
                    PropertyResident.relationship_type == RelationshipType.TENANT,
                    PropertyResident.is_active.is_(True),
                )
            )
        ).first()
        if active_tenant_exists is not None and other_active_owner is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Cannot deactivate the last active Owner while an active Tenant remains "
                "(Section 12 invariant)",
            )

    link.is_active = False
    link.end_date = date.today()
    await db.commit()
    await db.refresh(link)
    return link


async def list_property_residents(
    db: AsyncSession, society_id: uuid.UUID, property_id: uuid.UUID
) -> list[PropertyResident]:
    return (
        await db.execute(
            select(PropertyResident).where(
                PropertyResident.society_id == society_id,
                PropertyResident.property_id == property_id,
            )
        )
    ).scalars().all()


async def list_resident_properties(
    db: AsyncSession, society_id: uuid.UUID, resident_id: uuid.UUID
) -> list[PropertyResident]:
    """Section 12 — a Resident can own/rent multiple houses."""
    return (
        await db.execute(
            select(PropertyResident).where(
                PropertyResident.society_id == society_id,
                PropertyResident.resident_id == resident_id,
            )
        )
    ).scalars().all()
