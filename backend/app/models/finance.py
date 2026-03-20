from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime, timezone
import uuid

class IncomeEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    society_id: str
    title: str
    category: Literal["maintenance_collection", "scrape_sell", "lawn_rent", "parking_fee", "other"]
    amount: float
    entry_date: str  # YYYY-MM-DD
    description: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class IncomeEntryCreate(BaseModel):
    title: str
    category: str
    amount: float
    entry_date: str
    description: Optional[str] = None

class ExpenseBill(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    society_id: str
    title: str
    category: Literal["repair", "cleaning", "security", "electricity", "water", "other"]
    amount: float
    bill_date: str
    description: Optional[str] = None
    status: Literal["pending", "partially_verified", "verified", "rejected"] = "pending"
    created_by: str
    verified_by_ids: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ExpenseBillCreate(BaseModel):
    title: str
    category: str
    amount: float
    bill_date: str
    description: Optional[str] = None

class ExpenseVerification(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    expense_bill_id: str
    sub_admin_id: str
    sub_admin_name: str
    decision: Literal["pending", "approved", "rejected"] = "pending"
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ExpenseVerifyRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: Optional[str] = None

class Plan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    society_id: str
    title: str
    description: str
    amount: Optional[float] = None
    status: Literal["draft", "pending_approval", "approved", "rejected"] = "draft"
    rejection_reasons: List[dict] = []  # [{sub_admin_name, reason}]
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PlanCreate(BaseModel):
    title: str
    description: str
    amount: Optional[float] = None

class PlanApproval(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str
    sub_admin_id: str
    sub_admin_name: str
    decision: Literal["pending", "approved", "rejected"] = "pending"
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PlanApprovalRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: Optional[str] = None

class WalletTransaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    flat_bill_id: Optional[str] = None
    type: Literal["credit", "debit"]
    points: float
    balance_after: float
    description: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
