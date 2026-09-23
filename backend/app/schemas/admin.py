"""Admin self-signup (for an EXISTING society) + Platform Owner approval."""
import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator

from app.models.enums import HouseType, LocationType, RelationshipType, UserStatus


class AdminSignupIn(BaseModel):
    """Admin self-signup under an already-existing, ACTIVE society (created
    separately by the Platform Owner). Waits for Platform Owner approval —
    mirrors ResidentSignupIn's shape, but the approver is the Platform
    Owner rather than the society's own Admin.

    Two, mutually-exclusive, both-optional ways for an Admin who also
    lives here (Section 4 dual-role — ADMIN+RESIDENT) to describe that
    right at signup instead of a separate manual step after approval:

    1. `existing_property_id` + `existing_property_relationship` — the
       same self-service picker Resident signup uses (GET /societies/
       {id}/properties/public), for a unit the Platform Owner/Admin
       already set up. Owner or Tenant; Tenant needs the property to
       already have an active Owner (Section 12 invariant), same as
       ResidentSignupIn.
    2. `property_location_name`/`property_location_type`/`house_number`/
       `house_type`/`floor_number` (all-or-nothing) — describes a
       BRAND-NEW unit not yet on record (e.g. the Platform Owner hasn't
       mapped the society's structure yet), Owner only, since a just-
       described unit can never already have a Tenant on it.

    Neither is required — a pure administrator with no unit here leaves
    both blank. Nothing is created until Platform Owner approval
    activates the account, same as the ADMIN role itself."""

    full_name: str
    mobile: str
    email: str | None = None
    society_id: uuid.UUID

    existing_property_id: uuid.UUID | None = None
    existing_property_relationship: RelationshipType | None = None

    property_location_name: str | None = None
    property_location_type: LocationType | None = None
    house_number: str | None = None
    house_type: HouseType | None = None
    floor_number: int | None = None

    @model_validator(mode="after")
    def _property_fields_all_or_nothing(self) -> "AdminSignupIn":
        existing_fields = [self.existing_property_id is not None, self.existing_property_relationship is not None]
        if any(existing_fields) and not all(existing_fields):
            raise ValueError(
                "existing_property_id and existing_property_relationship must both be provided together, "
                "or both left blank"
            )
        existing_provided = all(existing_fields)

        new_unit_fields = (self.property_location_name, self.property_location_type, self.house_number, self.house_type)
        new_unit_provided_each = [f is not None for f in new_unit_fields]
        if any(new_unit_provided_each) and not all(new_unit_provided_each):
            raise ValueError(
                "property_location_name, property_location_type, house_number and house_type "
                "must all be provided together, or all left blank"
            )
        new_unit_provided = all(new_unit_provided_each)

        if existing_provided and new_unit_provided:
            raise ValueError(
                "Pick either an existing property (existing_property_id) or describe a new one "
                "(property_location_name/...), not both"
            )
        if new_unit_provided and self.house_type == HouseType.FLAT and self.floor_number is None:
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
