"""Property structure schemas — Section 11 (Flat/Bungalow, Wing/Row)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import HouseType, LocationType, PropertyStatus


class SocietyLocationCreateIn(BaseModel):
    name: str
    location_type: LocationType


class SocietyLocationUpdateIn(BaseModel):
    """Renaming a Wing/Row, or changing WING<->ROW — the latter is only
    allowed while no Property yet points at it (property_service.
    update_location enforces this; nothing in the DB itself would catch a
    Wing full of FLATs silently becoming a ROW)."""

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


class PropertyUpdateIn(BaseModel):
    """Correcting a typo made while mapping a society — wrong house number,
    wrong floor, or wrong Wing/Row — full replace, same convention as
    SocietyLocationUpdateIn."""

    location_id: uuid.UUID
    house_number: str
    house_type: HouseType
    floor_number: int | None = None

    @model_validator(mode="after")
    def _floor_required_for_flat(self) -> "PropertyUpdateIn":
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
# A society's towers are rarely identical (a taller tower, a shorter one, a
# wing with bigger flats and fewer per floor) — real total is bounded by the
# per-wing caps below anyway, this just stops one request from generating an
# absurd number of rows if several wings all max out their own fields.
_MAX_TOTAL_FLATS_PER_REQUEST = 5000


class FloorOverride(BaseModel):
    """One floor within a Wing that doesn't match that Wing's default
    flats_per_floor — e.g. the ground floor has 2 flats (lobby/parking
    eats the rest of the space) while every other floor has 4."""

    floor_number: int = Field(ge=1, le=_MAX_FLOORS_PER_TOWER)
    flats: int = Field(ge=1, le=_MAX_FLATS_PER_FLOOR)


class WingSpec(BaseModel):
    """One Wing's own shape — every Wing can differ (Tower A has 10 floors,
    Tower B has 15; one Wing has 2 flats/floor, another has 4).
    `flats_per_floor` is the default for every floor in this Wing;
    `floor_overrides` lists the exceptions (by floor_number) — most
    buildings are uniform except for a handful of odd floors, so this
    avoids having to spell out every single floor's count."""

    name: str | None = Field(default=None, max_length=100)
    floor_count: int = Field(ge=1, le=_MAX_FLOORS_PER_TOWER)
    flats_per_floor: int = Field(ge=1, le=_MAX_FLATS_PER_FLOOR)
    floor_overrides: list[FloorOverride] = []

    @model_validator(mode="after")
    def _overrides_are_valid(self) -> "WingSpec":
        floor_numbers = [fo.floor_number for fo in self.floor_overrides]
        if len(floor_numbers) != len(set(floor_numbers)):
            raise ValueError("floor_overrides has more than one entry for the same floor_number")
        out_of_range = [fn for fn in floor_numbers if fn > self.floor_count]
        if out_of_range:
            raise ValueError(
                f"floor_overrides names floor(s) {sorted(out_of_range)}, "
                f"but this Wing only has {self.floor_count} floor(s)"
            )
        return self

    def flats_on_floor(self, floor_number: int) -> int:
        for fo in self.floor_overrides:
            if fo.floor_number == floor_number:
                return fo.flats
        return self.flats_per_floor


class FlatsStructureIn(BaseModel):
    """Generates one Wing per entry in `wings`, each with its own
    floor_count x flats_per_floor grid of FLAT properties — every
    tower/floor/flat combination, all at once, in a single transaction.
    An entry with no `name` gets an auto-generated one ("Tower N", by
    position in the list)."""

    wings: list[WingSpec] = Field(min_length=1, max_length=_MAX_TOWERS)

    @model_validator(mode="after")
    def _total_within_cap(self) -> "FlatsStructureIn":
        total = sum(
            w.flats_on_floor(floor) for w in self.wings for floor in range(1, w.floor_count + 1)
        )
        if total > _MAX_TOTAL_FLATS_PER_REQUEST:
            raise ValueError(
                f"This would generate {total} flats in one request — "
                f"the limit is {_MAX_TOTAL_FLATS_PER_REQUEST}. Split it across a few requests."
            )
        return self


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
