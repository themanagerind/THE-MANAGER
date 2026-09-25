"""Manager To-Do schemas — Section 16."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import TodoStatus


class TaskSuggestionCreateIn(BaseModel):
    title: str


class TaskSuggestionOut(BaseModel):
    id: uuid.UUID
    title: str
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ManagerTodoCreateIn(BaseModel):
    manager_id: uuid.UUID
    task_suggestion_id: uuid.UUID
    task_date: date


class ManagerTodoOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    manager_id: uuid.UUID
    task_suggestion_id: uuid.UUID
    task_date: date
    status: TodoStatus
    assigned_by: uuid.UUID
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ManagerTodoStatusUpdateIn(BaseModel):
    status: TodoStatus


class ManagerDailyTaskSetIn(BaseModel):
    """The full set of task_suggestions that should be ON for this Manager
    — a checkbox list submits its whole current state, not one toggle at a
    time, so this replaces rather than adds to whatever was set before."""

    task_suggestion_ids: list[uuid.UUID]


class ManagerDailyTaskOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    manager_id: uuid.UUID
    task_suggestion_id: uuid.UUID
    task_title: str
    is_active: bool
    created_at: datetime
