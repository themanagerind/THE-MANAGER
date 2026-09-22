"""Expense bill schemas — Section 23."""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Decision, ExpenseBillStatus


class ExpenseBillCreateIn(BaseModel):
    title: str
    description: str | None = None
    amount: float
    category: str | None = None


class ExpenseBillOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    title: str
    description: str | None
    amount: float
    category: str | None
    status: ExpenseBillStatus
    created_by: uuid.UUID
    finalized_by: uuid.UUID | None
    finalized_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExpenseBillDecisionIn(BaseModel):
    decision: Decision
    reason: str | None = None


class ExpenseBillApprovalOut(BaseModel):
    id: uuid.UUID
    expense_bill_id: uuid.UUID
    sub_admin_id: uuid.UUID
    decision: Decision
    reason: str | None
    decided_at: datetime

    model_config = {"from_attributes": True}


class ExpenseBillStatusDetailOut(BaseModel):
    bill: ExpenseBillOut
    approve_count: int
    active_subadmin_count: int
    approvals_needed: int
