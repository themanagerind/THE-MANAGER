"""Notice schemas — Section 19 (society-wide only, no targeting)."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class NoticeCreateIn(BaseModel):
    title: str
    content: str


class NoticeOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    title: str
    content: str
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
