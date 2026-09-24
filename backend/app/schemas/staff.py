"""Manager/Security Guard staff accounts — Admin creates them directly.

Unlike Admin/Resident, a Manager or Security Guard is third-party hired
staff, not a flat owner/tenant — Section 4's ADMIN+RESIDENT dual-role
requirement doesn't apply here, so there's no property link and no
separate approval step; the Admin hiring them IS the approval (same
"brand-new ACTIVE account, no further gate" shape as
admin_change_service's Platform Owner path for a new Admin)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models.enums import Role, UserStatus

STAFF_ROLES = (Role.MANAGER, Role.SECURITY_GUARD)


class StaffCreateIn(BaseModel):
    full_name: str
    mobile: str
    email: str | None = None
    role: Role

    @field_validator("role")
    @classmethod
    def _role_must_be_staff(cls, v: Role) -> Role:
        if v not in STAFF_ROLES:
            raise ValueError("role must be MANAGER or SECURITY_GUARD")
        return v


class StaffOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    full_name: str
    mobile: str
    email: str | None
    role: Role
    status: UserStatus
    assigned_at: datetime
