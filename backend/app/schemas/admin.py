"""Admin self-signup (for an EXISTING society) + Platform Owner approval."""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import RelationshipType, UserStatus


class AdminSignupIn(BaseModel):
    """Admin self-signup under an already-existing, ACTIVE society (created
    separately by the Platform Owner). Waits for Platform Owner approval —
    mirrors ResidentSignupIn's shape, but the approver is the Platform
    Owner rather than the society's own Admin.

    `existing_property_id` + `existing_property_relationship` are
    mandatory (Section 4 dual-role — every Admin is ADMIN+RESIDENT): the
    same self-service picker Resident signup uses (GET /societies/{id}/
    properties/public), for a unit the Platform Owner has already mapped.
    Owner or Tenant; Tenant needs the property to already have an active
    Owner (Section 12 invariant), same as ResidentSignupIn. There is no
    "describe a brand-new unit" option here — the Platform Owner is
    expected to have mapped the society's Wings/Rows/flats before an
    Admin signs up against it. Nothing is created until Platform Owner
    approval activates the account, same as the ADMIN role itself."""

    full_name: str
    mobile: str
    email: str | None = None
    society_id: uuid.UUID

    existing_property_id: uuid.UUID
    existing_property_relationship: RelationshipType


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
