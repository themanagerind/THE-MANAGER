"""Property structure schemas — Section 11 (Flat/Bungalow, Wing/Row)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator

from app.models.enums import HouseType, LocationType, PropertyStatus


class SocietyLocationCreateIn(BaseModel):
    name: str
    location_type: LocationType


class SocietyLocationOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    name: str
    location_type: LocationType
    created_at: datetime

    model_config = {"from_attributes": True}


class PropertyCreateIn(BaseModel):
    location_id: uuid.UUID
    house_number: str
    house_type: HouseType
    floor_number: int | None = None

    @model_validator(mode="after")
    def _floor_required_for_flat(self) -> "PropertyCreateIn":
        # Section 11: FLAT -> floor mandatory; BUNGALOW -> floor optional.
        if self.house_type == HouseType.FLAT and self.floor_number is None:
            raise ValueError("floor_number is mandatory for FLAT")
        return self


class PropertyStatusUpdateIn(BaseModel):
    status: PropertyStatus


class PropertyOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    location_id: uuid.UUID
    house_number: str
    house_type: HouseType
    floor_number: int | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
