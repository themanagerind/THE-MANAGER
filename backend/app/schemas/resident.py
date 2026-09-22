"""Resident schemas — Section 9 (Resident), Section 12 (Property Occupancy)."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import RelationshipType, UserStatus


class ResidentSignupIn(BaseModel):
    """Resident self-signup within a society (Admin approves/rejects after)."""

    full_name: str
    mobile: str
    email: str | None = None
    society_id: uuid.UUID


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


class PropertyResidentOut(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    resident_id: uuid.UUID
    relationship_type: RelationshipType
    is_active: bool
    start_date: date | None
    end_date: date | None

    model_config = {"from_attributes": True}
