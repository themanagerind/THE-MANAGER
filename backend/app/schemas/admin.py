"""Admin self-signup (for an EXISTING society) + Platform Owner approval."""
import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator

from app.models.enums import RelationshipType, UserStatus


class AdminSignupIn(BaseModel):
    """Admin self-signup under an already-existing, ACTIVE society (created
    separately by the Platform Owner). Waits for Platform Owner approval —
    mirrors ResidentSignupIn's shape, but the approver is the Platform
    Owner rather than the society's own Admin.

    `existing_property_id` + `existing_property_relationship` are
    OPTIONAL (user-requested change — an Admin no longer has to prove/pick
    a unit at signup, or be asked whether they have one; only someone who
    already lives in the society becomes its Admin in practice, so the
    question was redundant). If given, both must be given together, the
    same self-service picker Resident signup uses (GET /societies/{id}/
    properties/public), for a unit the Platform Owner has already mapped
    — and signup grants the Section 4 ADMIN+RESIDENT dual-role immediately,
    same as before. If omitted, the Admin account gets ADMIN only; they can
    link a property (and pick up the RESIDENT role automatically) any time
    later via POST /residents/self-link — the Admin Properties page's
    "Link as Resident" action, which already handles the
    not-yet-a-Resident case (admin_service.link_admin_as_resident /
    resident_service). Owner or Tenant — same as ResidentSignupIn, a
    Tenant here does NOT require the property to already have an active
    Owner (Section 12 invariant); the account stays PENDING until
    Platform Owner review either way."""

    full_name: str
    mobile: str
    email: str | None = None
    society_id: uuid.UUID

    existing_property_id: uuid.UUID | None = None
    existing_property_relationship: RelationshipType | None = None

    @model_validator(mode="after")
    def _property_fields_are_both_or_neither(self) -> "AdminSignupIn":
        has_id = self.existing_property_id is not None
        has_relationship = self.existing_property_relationship is not None
        if has_id != has_relationship:
            raise ValueError(
                "existing_property_id and existing_property_relationship must be given together, or not at all"
            )
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
