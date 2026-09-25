"""Complaint schemas — Section 17."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ComplaintStatus


class ComplaintCreateIn(BaseModel):
    property_id: uuid.UUID
    category: str
    title: str
    description: str


class ComplaintOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    property_id: uuid.UUID
    resident_id: uuid.UUID
    category: str
    title: str
    description: str
    status: ComplaintStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class ComplaintStatusUpdateIn(BaseModel):
    status: ComplaintStatus


class ComplaintAssignIn(BaseModel):
    assigned_to: uuid.UUID  # must hold MANAGER role (Section 49.8)


class ComplaintAssignmentOut(BaseModel):
    id: uuid.UUID
    complaint_id: uuid.UUID
    assigned_to: uuid.UUID
    assigned_by: uuid.UUID
    assigned_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ComplaintRatingIn(BaseModel):
    rating: int = Field(ge=1, le=5)


class ComplaintRatingOut(BaseModel):
    id: uuid.UUID
    complaint_id: uuid.UUID
    resident_id: uuid.UUID
    manager_id: uuid.UUID
    rating: int
    created_at: datetime

    model_config = {"from_attributes": True}
