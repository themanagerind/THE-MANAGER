"""Amenity service — Section 20."""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import BookingStatus, Role
from app.models.operations import Amenity, AmenityBooking
from app.services.scope_service import resident_owns_or_rents_property, subadmin_has_scope_over_property


async def create_amenity(db: AsyncSession, society_id: uuid.UUID, name: str, description: str | None) -> Amenity:
    amenity = Amenity(society_id=society_id, name=name, description=description, is_active=True)
    db.add(amenity)
    await db.commit()
    await db.refresh(amenity)
    return amenity


async def list_amenities(db: AsyncSession, society_id: uuid.UUID) -> list[Amenity]:
    return (await db.execute(select(Amenity).where(Amenity.society_id == society_id))).scalars().all()


async def create_booking(
    db: AsyncSession, society_id: uuid.UUID, resident_id: uuid.UUID, amenity_id: uuid.UUID,
    property_id: uuid.UUID, booking_date, start_time, end_time,
) -> AmenityBooking:
    # CRITICAL fix (audit round-8): a Resident could previously book against
    # ANY property in their society, not just one they're linked to.
    if not await resident_owns_or_rents_property(db, resident_id, property_id, society_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You are not an active Owner/Tenant of this property"
        )

    amenity = (
        await db.execute(select(Amenity).where(Amenity.id == amenity_id, Amenity.society_id == society_id))
    ).scalar_one_or_none()
    if amenity is None or not amenity.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Amenity not found or inactive in this society")

    booking = AmenityBooking(
        society_id=society_id, amenity_id=amenity_id, property_id=property_id, resident_id=resident_id,
        booking_date=booking_date, start_time=start_time, end_time=end_time, status=BookingStatus.PENDING,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking


async def list_bookings(db: AsyncSession, society_id: uuid.UUID, skip: int = 0, limit: int = 20) -> tuple[list[AmenityBooking], int]:
    from sqlalchemy import func
    total = (await db.execute(select(func.count()).select_from(AmenityBooking).where(AmenityBooking.society_id == society_id))).scalar_one()
    rows = (
        await db.execute(
            select(AmenityBooking).where(AmenityBooking.society_id == society_id)
            .order_by(AmenityBooking.booking_date.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()
    return rows, total


async def list_my_bookings(db: AsyncSession, society_id: uuid.UUID, resident_id: uuid.UUID, skip: int = 0, limit: int = 20) -> tuple[list[AmenityBooking], int]:
    from sqlalchemy import func
    total = (
        await db.execute(
            select(func.count()).select_from(AmenityBooking)
            .where(AmenityBooking.society_id == society_id, AmenityBooking.resident_id == resident_id)
        )
    ).scalar_one()
    rows = (
        await db.execute(
            select(AmenityBooking).where(
                AmenityBooking.society_id == society_id, AmenityBooking.resident_id == resident_id
            ).order_by(AmenityBooking.booking_date.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()
    return rows, total


async def decide_booking(
    db: AsyncSession, society_id: uuid.UUID, decider_id: uuid.UUID, decider_role: Role,
    booking_id: uuid.UUID, approve: bool,
) -> AmenityBooking:
    booking = (
        await db.execute(
            select(AmenityBooking).where(AmenityBooking.id == booking_id, AmenityBooking.society_id == society_id)
        )
    ).scalar_one_or_none()
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found in this society")
    if booking.status != BookingStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Booking is already {booking.status.value}")

    if decider_role == Role.SUB_ADMIN and not await subadmin_has_scope_over_property(
        db, decider_id, booking.property_id, society_id
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Booking's property is outside your assigned scope")

    booking.status = BookingStatus.APPROVED if approve else BookingStatus.REJECTED
    booking.approved_by = decider_id
    await db.commit()
    await db.refresh(booking)
    return booking
