"""
Property/location service — Section 11.

The FLAT->WING / BUNGALOW->ROW consistency rule spans two tables
(properties.house_type vs society_locations.location_type), so it cannot be
a single-table CHECK constraint (see Schema Spec v1.3, `properties` table
note) — enforced here at the service layer, inside the same transaction as
the insert, exactly as the spec requires.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType
from app.models.identity import Property, SocietyLocation
from app.schemas.property import PropertyCreateIn, SocietyLocationCreateIn

# Section 11: FLAT belongs to a Wing, Bungalow belongs to a Row.
_EXPECTED_LOCATION_TYPE = {
    HouseType.FLAT: LocationType.WING,
    HouseType.BUNGALOW: LocationType.ROW,
}


async def create_location(
    db: AsyncSession, society_id: uuid.UUID, body: SocietyLocationCreateIn
) -> SocietyLocation:
    location = SocietyLocation(
        society_id=society_id, name=body.name, location_type=body.location_type
    )
    db.add(location)
    await db.commit()
    await db.refresh(location)
    return location


async def list_locations(db: AsyncSession, society_id: uuid.UUID) -> list[SocietyLocation]:
    return (
        await db.execute(select(SocietyLocation).where(SocietyLocation.society_id == society_id))
    ).scalars().all()


async def create_property(
    db: AsyncSession, society_id: uuid.UUID, body: PropertyCreateIn
) -> Property:
    location = (
        await db.execute(
            select(SocietyLocation).where(
                SocietyLocation.id == body.location_id,
                SocietyLocation.society_id == society_id,  # tenant isolation
            )
        )
    ).scalar_one_or_none()
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found in this society")

    expected = _EXPECTED_LOCATION_TYPE[body.house_type]
    if location.location_type != expected:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{body.house_type.value} must be under a {expected.value}, "
            f"but location '{location.name}' is a {location.location_type.value}",
        )

    prop = Property(
        society_id=society_id,
        location_id=body.location_id,
        house_number=body.house_number,
        house_type=body.house_type,
        floor_number=body.floor_number,
        status="ACTIVE",
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)
    return prop


async def list_properties(db: AsyncSession, society_id: uuid.UUID) -> list[Property]:
    return (
        await db.execute(select(Property).where(Property.society_id == society_id))
    ).scalars().all()


async def update_property_status(
    db: AsyncSession, society_id: uuid.UUID, property_id: uuid.UUID, new_status: str
) -> Property:
    """Admin-only ACTIVE/INACTIVE toggle. resident_owns_or_rents_property()
    (scope_service) checks this on every Resident-facing action (payments,
    complaints, visitors, amenities), so marking a property INACTIVE
    immediately blocks new activity on it without touching the underlying
    PropertyResident links."""
    prop = (
        await db.execute(
            select(Property).where(Property.id == property_id, Property.society_id == society_id)
        )
    ).scalar_one_or_none()
    if prop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Property not found in this society")

    prop.status = new_status
    await db.commit()
    await db.refresh(prop)
    return prop
