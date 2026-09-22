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

    model_config = {"from_attributes": True}
