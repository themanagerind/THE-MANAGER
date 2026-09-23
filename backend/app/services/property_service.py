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
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType
from app.models.identity import Property, PropertyResident, SocietyLocation
from app.schemas.property import (
    PropertyCreateIn,
    PropertyOut,
    PropertyUpdateIn,
    SocietyLocationCreateIn,
    SocietyLocationUpdateIn,
)

# Section 11: FLAT belongs to a Wing, Bungalow belongs to a Row. Public —
# also used by admin_service.signup_admin's optional property capture,
# which validates this same consistency rule without going through
# create_property (that commits internally; the signup flow needs
# everything in one transaction so a later failure rolls back cleanly).
EXPECTED_LOCATION_TYPE = {
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


async def update_location(
    db: AsyncSession, society_id: uuid.UUID, location_id: uuid.UUID, body: SocietyLocationUpdateIn
) -> SocietyLocation:
    """Renaming is always safe. Changing WING<->ROW is only safe while no
    Property yet points at this location — otherwise existing FLATs (or
    BUNGALOWs) would silently end up under the wrong location_type, which
    nothing else in the DB would catch (see SocietyLocationUpdateIn's
    docstring)."""
    location = (
        await db.execute(
            select(SocietyLocation).where(
                SocietyLocation.id == location_id, SocietyLocation.society_id == society_id
            )
        )
    ).scalar_one_or_none()
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found in this society")

    if body.location_type != location.location_type:
        in_use = (
            await db.execute(
                select(func.count()).select_from(Property).where(Property.location_id == location_id)
            )
        ).scalar_one()
        if in_use > 0:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Can't change type — {in_use} propert{'y' if in_use == 1 else 'ies'} already use this Wing/Row",
            )

    location.name = body.name
    location.location_type = body.location_type
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Another Wing/Row with that name and type already exists")
    await db.refresh(location)
    return location


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

    expected = EXPECTED_LOCATION_TYPE[body.house_type]
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
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"House number '{body.house_number}' is already in use in this society"
        )
    await db.refresh(prop)
    return prop


async def update_property(
    db: AsyncSession, society_id: uuid.UUID, property_id: uuid.UUID, body: PropertyUpdateIn
) -> Property:
    """Correcting a Wing/floor/house-number typo from the Society Mapping
    page's Flats-mapping step — full replace, same shape/validation as
    create_property above."""
    prop = (
        await db.execute(
            select(Property).where(Property.id == property_id, Property.society_id == society_id)
        )
    ).scalar_one_or_none()
    if prop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Property not found in this society")

    location = (
        await db.execute(
            select(SocietyLocation).where(
                SocietyLocation.id == body.location_id,
                SocietyLocation.society_id == society_id,
            )
        )
    ).scalar_one_or_none()
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found in this society")

    expected = EXPECTED_LOCATION_TYPE[body.house_type]
    if location.location_type != expected:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{body.house_type.value} must be under a {expected.value}, "
            f"but location '{location.name}' is a {location.location_type.value}",
        )

    prop.location_id = body.location_id
    prop.house_number = body.house_number
    prop.house_type = body.house_type
    prop.floor_number = body.floor_number
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"House number '{body.house_number}' is already in use in this society"
        )
    await db.refresh(prop)
    return prop


async def delete_property(db: AsyncSession, society_id: uuid.UUID, property_id: uuid.UUID) -> None:
    """Removing a wrongly-added Property from the Society Mapping page —
    only safe while nothing else (a Resident link, a payment, a
    complaint...) references it yet; those are enforced by FK constraints
    at the DB level, surfaced here as a 409 rather than a raw 500."""
    prop = (
        await db.execute(
            select(Property).where(Property.id == property_id, Property.society_id == society_id)
        )
    ).scalar_one_or_none()
    if prop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Property not found in this society")

    await db.delete(prop)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Can't delete — this property is already linked to a Resident, payment, or other record. "
            "Mark it INACTIVE instead if it shouldn't be used going forward.",
        )


def property_out(prop: Property, is_occupied: bool) -> PropertyOut:
    """PropertyOut.model_validate(prop) alone can't fill is_occupied — it's
    not a column on Property, it's computed by list_properties above."""
    out = PropertyOut.model_validate(prop)
    out.is_occupied = is_occupied
    return out


async def list_properties(db: AsyncSession, society_id: uuid.UUID) -> list[tuple[Property, bool]]:
    """Each row paired with whether an active Resident is currently linked
    — the Structure Overview diagram's occupied/vacant coloring, computed
    once here so every caller (Platform Owner, Admin, Resident) gets it for
    free instead of each re-deriving it."""
    occupied = (
        select(func.count())
        .select_from(PropertyResident)
        .where(PropertyResident.property_id == Property.id, PropertyResident.is_active.is_(True))
        .correlate(Property)
        .scalar_subquery()
    )
    rows = await db.execute(
        select(Property, (occupied > 0)).where(Property.society_id == society_id)
    )
    return [(prop, bool(is_occupied)) for prop, is_occupied in rows.all()]


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
