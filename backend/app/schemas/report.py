"""Reports — Admin/Sub-admin/Resident dashboards (v1.5 addition).

Three read-only views, scoped per role: a Monthly Maintenance summary,
a Manager task-completion + complaint-resolution performance scorecard
(feeding the rating a Resident can give — see complaint_service.
rate_complaint), and a Resident's own list of resolved complaints
still open to be rated. More report types get added here as they come
up — this module is meant to be the one place they all live.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ComplaintStatus


class MaintenanceSummaryOut(BaseModel):
    properties_count: int
    total_billed: float
    total_collected: float
    total_pending: float
    overdue_count: int
    total_overdue_amount: float
    collection_rate_percent: float


class ManagerPerformanceOut(BaseModel):
    manager_id: uuid.UUID
    manager_name: str
    tasks_total: int
    tasks_completed: int
    complaints_assigned: int
    complaints_resolved: int
    average_rating: float | None
    ratings_count: int


class MyComplaintForRatingOut(BaseModel):
    complaint_id: uuid.UUID
    title: str
    category: str
    status: ComplaintStatus
    created_at: datetime
    resolved_manager_id: uuid.UUID | None
    resolved_manager_name: str | None
    rating: int | None
    rated_at: datetime | None
