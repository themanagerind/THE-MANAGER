"""Society request/response schemas — Section 5/6/25."""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import SocietyStatus


class SocietySignupIn(BaseModel):
    """Admin self-signup for a new society (Section 26: Admin approval flow).
    Creates the Society (PENDING) and the Admin user (PENDING) together —
    both wait for Platform Owner approval before either becomes usable."""

    society_name: str
    society_code: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None

    admin_full_name: str
    admin_mobile: str
    admin_email: str | None = None


class SocietySignupOut(BaseModel):
    society_id: uuid.UUID
    admin_user_id: uuid.UUID
    message: str = "Submitted — awaiting Platform Owner approval"


class SocietyOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    status: SocietyStatus
    address: str | None
    city: str | None
    state: str | None
    pincode: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SocietyStatusUpdateIn(BaseModel):
    status: SocietyStatus
