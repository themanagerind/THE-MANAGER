"""Account report schemas — Section 13.0/13.1."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import EntrySource, EntryType


class AccountEntryCreateIn(BaseModel):
    """MANUAL entries only — Admin-only (Section 13.1)."""

    entry_type: EntryType
    title: str
    description: str | None = None
    amount: float
    entry_date: date


class AccountEntryUpdateIn(BaseModel):
    title: str | None = None
    description: str | None = None
    amount: float | None = None
    entry_date: date | None = None


class AccountEntryOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    entry_type: EntryType
    source: EntrySource
    title: str
    description: str | None
    amount: float
    entry_date: date
    is_edited: bool
    last_edited_at: datetime | None
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class BalanceSummaryOut(BaseModel):
    """Section 13.0 — 2-column ledger: Income, Expense, Balance = Income - Expense."""

    total_income: float
    total_expense: float
    balance: float
