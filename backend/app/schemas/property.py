"""Property structure schemas — Section 11 (Flat/Bungalow, Wing/Row)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

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
    floors_above_ground: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Platform Owner bulk structure generation ------------------------------
# A Platform Owner defining a society's shape in bulk from the Societies
# page's Edit modal, instead of adding each Wing/Row and each Property by
# hand. Caps below are generous but finite — a typo (e.g. "500" floors)
# shouldn't be able to insert an unbounded number of rows in one request.

_MAX_TOWERS = 50
_MAX_FLOORS_PER_TOWER = 100
_MAX_FLATS_PER_FLOOR = 50
_MAX_ROWS = 100
_MAX_HOUSES_PER_ROW = 200
_MAX_FLOORS_ABOVE_GROUND = 20


class FlatsStructureIn(BaseModel):
    """Generates `tower_count` Wings, each with `floors_per_tower` floors of
    `flats_per_floor` FLAT properties — every tower/floor/flat combination,
    all at once, in a single transaction."""

    tower_count: int = Field(ge=1, le=_MAX_TOWERS)
    floors_per_tower: int = Field(ge=1, le=_MAX_FLOORS_PER_TOWER)
    flats_per_floor: int = Field(ge=1, le=_MAX_FLATS_PER_FLOOR)


class BungalowStructureIn(BaseModel):
    """Generates `row_count` Rows, each with `houses_per_row` BUNGALOW
    properties — every house starts at its (always-implied) ground floor
    only; additional storeys are set per-house afterward via
    PropertyFloorsUpdateIn, since that varies house to house."""

    row_count: int = Field(ge=1, le=_MAX_ROWS)
    houses_per_row: int = Field(ge=1, le=_MAX_HOUSES_PER_ROW)


class PropertyFloorsUpdateIn(BaseModel):
    """How many storeys are built above a BUNGALOW house's (always-implied)
    ground floor — 0 means ground floor only."""

    floors_above_ground: int = Field(ge=0, le=_MAX_FLOORS_ABOVE_GROUND)
