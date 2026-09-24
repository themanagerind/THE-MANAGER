"""Amenities endpoints — Section 20."""
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.amenity import (
    AmenityBookingCreateIn,
    AmenityBookingDecisionIn,
    AmenityBookingOut,
    AmenityCreateIn,
    AmenityOut,
    AmenitySlotOut,
)
from app.schemas.pagination import Page, Pagination, pagination_params
from app.services import amenity_service

router = APIRouter(prefix="/amenities", tags=["amenities"])


@router.post("", response_model=AmenityOut)
async def create_amenity(
    body: AmenityCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> AmenityOut:
    amenity = await amenity_service.create_amenity(db, current.society_id, body.name, body.description)
    return AmenityOut.model_validate(amenity)


@router.get("", response_model=list[AmenityOut])
async def list_amenities(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[
        CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.RESIDENT))
    ],
) -> list[AmenityOut]:
    amenities = await amenity_service.list_amenities(db, current.society_id)
    return [AmenityOut.model_validate(a) for a in amenities]


@router.get("/{amenity_id}/slots", response_model=list[AmenitySlotOut])
async def get_occupied_slots(
    amenity_id: uuid.UUID,
    booking_date: date,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[
        CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.RESIDENT))
    ],
) -> list[AmenitySlotOut]:
    """Already-booked/requested slots for this amenity on this date, so a
    Resident can see what's taken before submitting a request instead of
    finding out only after a 409 (or, before this fix, not finding out at
    all — two Residents could book the same slot with no warning)."""
    slots = await amenity_service.list_occupied_slots(db, current.society_id, amenity_id, booking_date)
    return [AmenitySlotOut.model_validate(s) for s in slots]


@router.post("/bookings", response_model=AmenityBookingOut)
async def create_booking(
    body: AmenityBookingCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> AmenityBookingOut:
    booking = await amenity_service.create_booking(
        db, current.society_id, current.user_id, body.amenity_id, body.property_id,
        body.booking_date, body.start_time, body.end_time,
    )
    return AmenityBookingOut.model_validate(booking)


@router.get("/bookings", response_model=Page[AmenityBookingOut])
async def list_bookings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.RESIDENT))],
    pagination: Annotated[Pagination, Depends(pagination_params)],
) -> Page[AmenityBookingOut]:
    if current.active_role == Role.RESIDENT:
        bookings, total = await amenity_service.list_my_bookings(
            db, current.society_id, current.user_id, pagination.skip, pagination.limit
        )
    else:
        bookings, total = await amenity_service.list_bookings(db, current.society_id, pagination.skip, pagination.limit)
    return Page(items=[AmenityBookingOut.model_validate(b) for b in bookings], total=total, skip=pagination.skip, limit=pagination.limit)


@router.post("/bookings/{booking_id}/decision", response_model=AmenityBookingOut)
async def decide_booking(
    booking_id: uuid.UUID,
    body: AmenityBookingDecisionIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN))],
) -> AmenityBookingOut:
    """Admin (any scope) or Sub-admin (property's scope) — Section 20."""
    booking = await amenity_service.decide_booking(
        db, current.society_id, current.user_id, current.active_role, booking_id, body.approve
    )
    return AmenityBookingOut.model_validate(booking)
