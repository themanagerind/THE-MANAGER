"""Admin change request schemas — Platform Owner-initiated replacement,
and Admin self-resignation (picking an existing Resident/Sub-admin as
successor), both requiring unanimous Sub-admin sign-off. See
app/models/identity.py's AdminChangeRequest/AdminChangeApproval."""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Role, RoleRequestStatus


class AdminChangeRequestIn(BaseModel):
    society_id: uuid.UUID
    new_admin_full_name: str
    new_admin_mobile: str
    new_admin_email: str | None = None


class AdminResignationIn(BaseModel):
    """Admin-initiated — society_id/old_admin_id are the caller's own
    (inferred from the auth token), not passed in the body."""

    new_admin_user_id: uuid.UUID


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
    new_admin_user_id: uuid.UUID | None
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


class ResignationCandidateOut(BaseModel):
    """A society's active Residents/Sub-admins an Admin can pick as their
    successor — role_label is whichever of the two is more specific
    (SUB_ADMIN over RESIDENT) since a Sub-admin always also holds
    RESIDENT (subadmin_service.promote_to_subadmin adds it alongside, not
    instead of), so showing both would just be noise."""

    id: uuid.UUID
    full_name: str
    mobile: str
    role_label: str


class RoleHistoryOut(BaseModel):
    """One row per ADMIN/SUB_ADMIN role assignment a society has ever
    had, active or long since revoked — user_roles.assigned_at/
    revoked_at IS the work-period history, this just surfaces it."""

    id: uuid.UUID
    full_name: str
    mobile: str
    role: Role
    assigned_at: datetime
    revoked_at: datetime | None
