"""Sub-admin schemas — Section 6 (Admin promotes), Section 7 (Sub-admin scope)."""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import RoleRequestStatus


class PromoteToSubAdminIn(BaseModel):
    resident_id: uuid.UUID
    location_ids: list[uuid.UUID]  # one or more wings/rows (Section 7)


class AssignScopeIn(BaseModel):
    location_id: uuid.UUID


class SubAdminScopeOut(BaseModel):
    id: uuid.UUID
    sub_admin_id: uuid.UUID
    location_id: uuid.UUID
    assigned_by: uuid.UUID
    assigned_at: datetime
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class ResignationRequestIn(BaseModel):
    reason: str | None = None


class ResignationDecisionIn(BaseModel):
    approve: bool
    decision_reason: str | None = None


class RoleRequestOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    society_id: uuid.UUID
    status: RoleRequestStatus
    reason: str | None
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    decision_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
