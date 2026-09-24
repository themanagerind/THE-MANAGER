"""Admin change request schemas — Platform Owner-initiated Admin
replacement, requiring unanimous Sub-admin sign-off (see
app/models/identity.py's AdminChangeRequest/AdminChangeApproval)."""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import RoleRequestStatus


class AdminChangeRequestIn(BaseModel):
    society_id: uuid.UUID
    new_admin_full_name: str
    new_admin_mobile: str
    new_admin_email: str | None = None


class AdminChangeRequestOut(BaseModel):
    """Not built via model_validate — approvals_total/approvals_done are
    a computed count, not columns, so the service constructs this as a
    plain dict (AdminChangeRequestOut(**row)), same pattern as
    SubAdminAssignmentOut."""

    id: uuid.UUID
    society_id: uuid.UUID
    old_admin_id: uuid.UUID
    new_admin_full_name: str
    new_admin_mobile: str
    new_admin_email: str | None
    status: RoleRequestStatus
    initiated_by: uuid.UUID
    new_admin_id: uuid.UUID | None
    created_at: datetime
    decided_at: datetime | None
    approvals_total: int
    approvals_done: int


class AdminChangeDecisionIn(BaseModel):
    approve: bool


class PendingAdminChangeApprovalOut(BaseModel):
    """A Sub-admin's own pending-decision dashboard card — denormalized
    with the request's own new-admin fields so the Sub-admin can see who
    they're being asked to approve without a separate lookup."""

    approval_id: uuid.UUID
    request_id: uuid.UUID
    society_id: uuid.UUID
    new_admin_full_name: str
    new_admin_mobile: str
    created_at: datetime
