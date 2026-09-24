"""User response schema — shared across modules."""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Role, UserStatus


class UserOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID | None
    full_name: str
    mobile: str
    email: str | None
    status: UserStatus
    roles: list[Role]
    created_at: datetime
    # True when a custom profile photo is set — GET /users/me/avatar fetches
    # the actual bytes (same authenticated-file pattern as payment proofs).
    has_avatar: bool = False

    model_config = {"from_attributes": True}


class ProfileUpdateIn(BaseModel):
    """Self-service profile edit (GET/PATCH /users/me) — full_name/email
    only. `mobile` is deliberately not editable here: it's the OTP login
    identity and is uniqueness-constrained per society (and globally for
    Platform Owner rows), so changing it needs its own re-verification
    flow, not a plain profile edit — out of scope for this endpoint."""

    full_name: str
    email: str | None = None
