"""Admin self-signup (for an EXISTING society) + Platform Owner approval."""
import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator

from app.models.enums import HouseType, LocationType, UserStatus


class AdminSignupIn(BaseModel):
    """Admin self-signup under an already-existing, ACTIVE society (created
    separately by the Platform Owner). Waits for Platform Owner approval —
    mirrors ResidentSignupIn's shape, but the approver is the Platform
    Owner rather than the society's own Admin.

    The property_* fields are optional and all-or-nothing: an Admin who
    also owns a unit in this society can describe it right here instead
    of using the separate POST /residents/self-link flow after approval
    (Section 4 dual-role — ADMIN+RESIDENT). Owner only — this always
    describes a brand-new unit, which can never have a Tenant without an
    existing Owner already on it (Section 12 invariant); linking as
    Tenant, or as Owner of a unit that already exists, goes through
    self-link instead, which picks from real existing properties. Nothing
    is created until Platform Owner approval activates the account, same
    as the ADMIN role itself."""

    full_name: str
    mobile: str
    email: str | None = None
    society_id: uuid.UUID

    property_location_name: str | None = None
    property_location_type: LocationType | None = None
    house_number: str | None = None
    house_type: HouseType | None = None
    floor_number: int | None = None

    @model_validator(mode="after")
    def _property_fields_all_or_nothing(self) -> "AdminSignupIn":
        required = (self.property_location_name, self.property_location_type, self.house_number, self.house_type)
        provided = [f is not None for f in required]
        if any(provided) and not all(provided):
            raise ValueError(
                "property_location_name, property_location_type, house_number and house_type "
                "must all be provided together, or all left blank"
            )
        if self.house_type == HouseType.FLAT and self.floor_number is None:
            raise ValueError("floor_number is mandatory for FLAT")
        return self


class AdminOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID | None
    full_name: str
    mobile: str
    email: str | None
    status: UserStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminApprovalIn(BaseModel):
    approve: bool
