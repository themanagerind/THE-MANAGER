"""Account report schemas — Section 13.0/13.1, plus the Account Heading
catalog extension (v1.7/v1.9)."""
import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, field_validator

from app.models.enums import EntrySource, EntryType

_HAS_LETTER = re.compile(r"[A-Za-z]")


def _validate_heading_title(v: str) -> str:
    """A heading is a category label, not a number — this is exactly the
    mistake that prompted it (someone typed an amount like "3000" into
    the heading box instead of a real name). Doesn't block mixed
    alphanumeric titles like "24x7 Security", only ones with no letters
    at all."""
    v = v.strip()
    if len(v) < 3:
        raise ValueError("Heading must be at least 3 characters long")
    if not _HAS_LETTER.search(v):
        raise ValueError("Heading must contain letters — looks like you typed a number/amount by mistake")
    return v


class AccountHeadingCreateIn(BaseModel):
    entry_type: EntryType
    title: str

    @field_validator("title")
    @classmethod
    def _title_must_look_like_a_heading(cls, v: str) -> str:
        return _validate_heading_title(v)


class AccountHeadingUpdateIn(BaseModel):
    """Renames a heading — entry_type is fixed (not editable: changing it
    could make the catalog inconsistent for whichever Income/Expense
    dropdown it was already being picked from). Safe to allow renaming
    at all: AccountEntry.title is a snapshot taken at creation/edit time,
    not a live reference, so this never retroactively changes any
    already-created entry's displayed title."""

    title: str

    @field_validator("title")
    @classmethod
    def _title_must_look_like_a_heading(cls, v: str) -> str:
        return _validate_heading_title(v)


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


class SettleExpenseBillIn(BaseModel):
    """Admin settles an APPROVED expense bill into the Accounts ledger
    (redesign, user-requested) — picks a heading, and an amount that
    can't exceed the bill's own approved amount (enforced in
    account_entry_service.settle_expense_bill). Replaces the old
    automatic post-on-approval behaviour."""

    expense_bill_id: uuid.UUID
    heading_id: uuid.UUID
    amount: float
    entry_date: date
    description: str | None = None
