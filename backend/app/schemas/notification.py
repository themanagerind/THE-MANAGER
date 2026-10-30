"""Resident notification schemas — Phase 1 in-app notifications
(user-requested). No input/create schema: rows are only ever created
server-side by notification_service.generate_overdue_notifications
(the cron script), never directly by a client."""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import NotificationType


class ResidentNotificationOut(BaseModel):
    id: uuid.UUID
    type: NotificationType
    title: str
    message: str
    related_due_id: uuid.UUID | None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountOut(BaseModel):
    count: int
