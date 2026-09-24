"""Resident schemas — Section 9 (Resident), Section 12 (Property Occupancy)."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import RelationshipType, RoleRequestStatus, UserStatus


class ResidentSignupIn(BaseModel):
    """Resident self-signup within a society (Admin approves/rejects after).
    property_id/relationship_type are required, not a separate post-
    approval step — the Resident picks their own house (from the public,
    already-on-record property list — GET /societies/{id}/properties/
    public) and whether they're Owner or Tenant right at signup, the same
    for a Flats or Bungalow society. Unlike the Admin-driven property-
    links flow, a Tenant signup here does NOT require the property to
    already have an active Owner (Section 12 invariant) — the account
    stays PENDING until the Admin reviews it, so the Admin judges the
    real-world situation at approval time instead."""

    full_name: str
    mobile: str
    email: str | None = None
    society_id: uuid.UUID
    property_id: uuid.UUID
    relationship_type: RelationshipType


class ResidentOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID | None
    full_name: str
    mobile: str
    email: str | None
    status: UserStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class ResidentApprovalIn(BaseModel):
    approve: bool
    rejection_reason: str | None = None


class PropertyResidentLinkIn(BaseModel):
    """Links an already-approved Resident to a property as Owner or Tenant
    (Section 12: multiple owners, owner+tenant coexist, resident can have
    multiple properties)."""

    property_id: uuid.UUID
    resident_id: uuid.UUID
    relationship_type: RelationshipType
    start_date: date | None = None


class AdminSelfResidentLinkIn(BaseModel):
    """Admin links THEMSELVES to a property in their own society as Owner
    or Tenant (Section 4: UserRole is explicitly a dual-role model —
    "ADMIN+RESIDENT, SUB_ADMIN+RESIDENT etc."). No `resident_id` — the
    caller's own user_id is used, and a RESIDENT role is granted on it if
    they don't already hold one, same pattern as
    subadmin_service.promote_to_subadmin adding SUB_ADMIN to an existing
    Resident."""

    property_id: uuid.UUID
    relationship_type: RelationshipType


class PropertyResidentOut(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    resident_id: uuid.UUID
    relationship_type: RelationshipType
    is_active: bool
    start_date: date | None
    end_date: date | None
    owner_contact_name: str | None
    owner_contact_mobile: str | None

    model_config = {"from_attributes": True}


class OwnerContactUpdateIn(BaseModel):
    """A Tenant recording the Owner's contact details themselves, from
    their own Profile page (resident_service.update_owner_contact) — free
    text, not a real account. There may be no Owner account in the system
    at all to look this up from (Section 12 invariant not enforced on
    self-service signup/request paths), so this is the only record of who
    the Owner actually is. Both fields optional — either can be cleared by
    passing an empty string/null."""

    owner_contact_name: str | None = None
    owner_contact_mobile: str | None = None


class PropertyLinkRequestIn(BaseModel):
    """An already-ACTIVE Resident, from their own Profile page, requesting
    to link themselves to an (additional) property — Owner or Tenant.
    Unlike the Admin-driven property-links flow, this stays PENDING until
    the Admin approves it (see PropertyLinkRequestOut/DecisionIn below)."""

    property_id: uuid.UUID
    relationship_type: RelationshipType
    reason: str | None = None


class PropertyLinkRequestOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    resident_id: uuid.UUID
    property_id: uuid.UUID
    relationship_type: RelationshipType
    status: RoleRequestStatus
    reason: str | None
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    decision_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PropertyLinkRequestDecisionIn(BaseModel):
    approve: bool
    decision_reason: str | None = None
