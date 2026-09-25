"""Account report schemas — Section 13.0/13.1, plus the Account Heading
catalog extension (v1.7)."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import EntrySource, EntryType


class AccountHeadingCreateIn(BaseModel):
    entry_type: EntryType
    title: str


class AccountHeadingOut(BaseModel):
    id: uuid.UUID
    entry_type: EntryType
    title: str
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountEntryCreateIn(BaseModel):
    """MANUAL entries only — Admin-only (Section 13.1). heading_id must
    resolve to an AccountHeading whose entry_type matches; the entry's
    title is taken from the heading, not free-typed."""

    entry_type: EntryType
    heading_id: uuid.UUID
    description: str | None = None
    amount: float
    entry_date: date


class AccountEntryUpdateIn(BaseModel):
    heading_id: uuid.UUID | None = None
    description: str | None = None
    amount: float | None = None
    entry_date: date | None = None


class AccountEntryOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    entry_type: EntryType
    source: EntrySource
    heading_id: uuid.UUID | None
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
