"""Admin change request schemas — Platform Owner-initiated replacement,
and Admin self-resignation (picking an existing Resident/Sub-admin as
successor), both requiring unanimous Sub-admin sign-off. See
app/models/identity.py's AdminChangeRequest/AdminChangeApproval."""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Role, RoleRequestStatus


class AdminChangeRequestIn(BaseModel):
    """Platform Owner picks the incoming Admin either of two ways:
    `new_admin_user_id` set — an existing active Resident/Sub-admin in
    that society (the normal path now that the picker lists them); or
    the three manual fields set — a brand-new person with no account yet
    in the system. Exactly one of the two must be provided; the service
    layer enforces this (a Pydantic validator can't see the DB to tell
    "existing user" from "new person" apart on its own)."""

    society_id: uuid.UUID
    new_admin_user_id: uuid.UUID | None = None
    new_admin_full_name: str | None = None
    new_admin_mobile: str | None = None
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
    """A society's active Residents/Sub-admins that can be picked as the
    new Admin — used both by an Admin's own resignation picker and by
    the Platform Owner's Change Admin picker (app/services/
    admin_change_service.list_admin_change_candidates). role_label is
    whichever of the two is more specific (SUB_ADMIN over RESIDENT)
    since a Sub-admin always also holds RESIDENT (subadmin_service.
    promote_to_subadmin adds it alongside, not instead of), so showing
    both would just be noise. house_number/floor_number/location_name
    come from the candidate's active property link, if any — lets the
    picker be searched/filtered by Wing/Row, floor, or flat number."""

    id: uuid.UUID
    full_name: str
    mobile: str
    role_label: str
    house_number: str | None = None
    floor_number: int | None = None
    location_id: uuid.UUID | None = None
    location_name: str | None = None


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
