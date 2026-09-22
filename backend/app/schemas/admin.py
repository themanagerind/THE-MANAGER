"""Admin self-signup (for an EXISTING society) + Platform Owner approval."""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import UserStatus


class AdminSignupIn(BaseModel):
    """Admin self-signup under an already-existing, ACTIVE society (created
    separately by the Platform Owner). Waits for Platform Owner approval —
    mirrors ResidentSignupIn's shape, but the approver is the Platform
    Owner rather than the society's own Admin."""

    full_name: str
    mobile: str
    email: str | None = None
    society_id: uuid.UUID


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
