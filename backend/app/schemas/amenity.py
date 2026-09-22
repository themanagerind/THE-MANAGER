"""Amenity schemas — Section 20."""
import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, model_validator

from app.models.enums import BookingStatus


class AmenityCreateIn(BaseModel):
    name: str
    description: str | None = None


class AmenityOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    name: str
    description: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class AmenityBookingCreateIn(BaseModel):
    amenity_id: uuid.UUID
    property_id: uuid.UUID
    booking_date: date
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _time_range(self) -> "AmenityBookingCreateIn":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class AmenityBookingOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    amenity_id: uuid.UUID
    property_id: uuid.UUID
    resident_id: uuid.UUID
    booking_date: date
    start_time: time
    end_time: time
    status: BookingStatus
    approved_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AmenityBookingDecisionIn(BaseModel):
    approve: bool
