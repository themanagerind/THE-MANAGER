"""Amenity service — Section 20."""
import uuid
from datetime import date, time

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import BookingStatus, Role
from app.models.operations import Amenity, AmenityBooking
from app.services.scope_service import resident_owns_or_rents_property, subadmin_has_scope_over_property

# A slot still counts as taken while it's awaiting a decision — otherwise
# two Residents could both get PENDING bookings for the same overlapping
# time and only find out one was rejected after the fact.
_BLOCKING_STATUSES = (BookingStatus.PENDING, BookingStatus.APPROVED)


async def _overlapping_bookings(
    db: AsyncSession, amenity_id: uuid.UUID, booking_date: date, start_time: time, end_time: time,
    statuses: tuple[BookingStatus, ...] = _BLOCKING_STATUSES, exclude_booking_id: uuid.UUID | None = None,
) -> list[AmenityBooking]:
    query = select(AmenityBooking).where(
        AmenityBooking.amenity_id == amenity_id,
        AmenityBooking.booking_date == booking_date,
        AmenityBooking.status.in_(statuses),
        AmenityBooking.start_time < end_time,
        AmenityBooking.end_time > start_time,
    )
    if exclude_booking_id is not None:
        query = query.where(AmenityBooking.id != exclude_booking_id)
    return (await db.execute(query)).scalars().all()


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

    # Two Residents could otherwise both land a PENDING booking for the same
    # overlapping slot with no indication until an Admin decides one of them.
    if await _overlapping_bookings(db, amenity_id, booking_date, start_time, end_time):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This slot is already booked or pending approval for this amenity. Please choose another time.",
        )

    booking = AmenityBooking(
        society_id=society_id, amenity_id=amenity_id, property_id=property_id, resident_id=resident_id,
        booking_date=booking_date, start_time=start_time, end_time=end_time, status=BookingStatus.PENDING,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking


async def list_occupied_slots(
    db: AsyncSession, society_id: uuid.UUID, amenity_id: uuid.UUID, booking_date: date,
) -> list[AmenityBooking]:
    """Every PENDING/APPROVED booking for this amenity on this date, so a
    Resident can see which times are already taken before requesting one —
    not just find out after submitting (the bug this fixes). Returned via
    AmenitySlotOut, which deliberately drops resident_id: a Resident should
    see a slot is booked, not who booked it."""
    return (
        await db.execute(
            select(AmenityBooking).where(
                AmenityBooking.society_id == society_id,
                AmenityBooking.amenity_id == amenity_id,
                AmenityBooking.booking_date == booking_date,
                AmenityBooking.status.in_(_BLOCKING_STATUSES),
            ).order_by(AmenityBooking.start_time)
        )
    ).scalars().all()


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

    # create_booking already blocks a new request from overlapping an
    # existing PENDING/APPROVED one, but two PENDING requests for the same
    # slot can still both reach here (e.g. submitted in the same instant,
    # before either was decided) — don't let both get approved.
    if approve and await _overlapping_bookings(
        db, booking.amenity_id, booking.booking_date, booking.start_time, booking.end_time,
        statuses=(BookingStatus.APPROVED,), exclude_booking_id=booking.id,
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Another booking for this amenity's slot has already been approved.",
        )

    booking.status = BookingStatus.APPROVED if approve else BookingStatus.REJECTED
    booking.approved_by = decider_id
    await db.commit()
    await db.refresh(booking)
    return booking
