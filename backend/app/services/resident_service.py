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
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RelationshipType, Role, UserStatus
from app.models.identity import Property, PropertyResident, User, UserRole
from app.schemas.resident import PropertyResidentLinkIn, ResidentSignupIn


async def signup_resident(db: AsyncSession, body: ResidentSignupIn) -> User:
    resident = User(
        society_id=body.society_id,
        full_name=body.full_name,
        mobile=body.mobile,
        email=body.email,
        status=UserStatus.PENDING,
    )
    db.add(resident)
    await db.flush()
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


async def _has_active_owner(db: AsyncSession, property_id: uuid.UUID) -> bool:
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

    if body.relationship_type == RelationshipType.TENANT and not await _has_active_owner(
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
