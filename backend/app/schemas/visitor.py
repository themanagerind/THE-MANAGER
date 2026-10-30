"""Visitor schemas — Section 18, transitions per Section 49.13."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import VisitorStatus


class VisitorPreApproveIn(BaseModel):
    property_id: uuid.UUID
    visitor_name: str
    visitor_mobile: str | None = None
    visit_date: date
    purpose: str | None = None


class VisitorOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    property_id: uuid.UUID
    resident_id: uuid.UUID
    visitor_name: str
    visitor_mobile: str | None
    visit_date: date
    status: VisitorStatus
    purpose: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class GuardVisitorOut(BaseModel):
    """Section 21 data-boundary: Guard sees only what's needed for
    visitor/security purposes — no financial/private resident data."""

    id: uuid.UUID
    property_house_number: str
    visitor_name: str
    visitor_mobile: str | None
    visit_date: date
    status: VisitorStatus


class VisitorLogOut(BaseModel):
    id: uuid.UUID
    visitor_id: uuid.UUID
    guard_id: uuid.UUID
    entry_at: datetime | None
    exit_at: datetime | None
    notes: str | None

    model_config = {"from_attributes": True}
