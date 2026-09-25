"""
Accounts / Ledger — Schema Spec v1.3, Section 2.3.

Tables: account_entries, account_entry_edit_history, account_headings.
This resolves the forward reference from
payment_corrections.ledger_adjustment_entry_id (app/models/payments.py).
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import EntrySource, EntryType
from app.models.mixins import CreatedAtOnlyMixin, TimestampMixin, UUIDPKMixin
from app.models.pg_enum import pg_enum


class AccountHeading(Base, UUIDPKMixin, CreatedAtOnlyMixin):
    """Platform-global catalog of Income/Expense headings (v1.7) — Admin
    picks one of these instead of free-typing a title when adding a
    MANUAL account entry, same shape as manager_todo_service's
    TaskSuggestion catalog: add-only (no edit/deactivate), and any
    Admin's addition is visible to every society's Admin. Seeded with
    headings universal to Indian housing-society bookkeeping (0015);
    Admin can add more from the "Add entry" screen at any time."""

    __tablename__ = "account_headings"

    entry_type: Mapped[EntryType] = mapped_column(
        pg_enum(EntryType, "entry_type_enum"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("entry_type", "title", name="ux_account_headings_type_title"),
    )


class AccountEntry(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "account_entries"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    entry_type: Mapped[EntryType] = mapped_column(
        pg_enum(EntryType, "entry_type_enum"), nullable=False
    )
    source: Mapped[EntrySource] = mapped_column(
        pg_enum(EntrySource, "entry_source_enum"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # Set for MANUAL entries (mirrors the picked AccountHeading's title at
    # creation/edit time — heading rename isn't possible since the catalog
    # is add-only, so this never drifts). NULL for system-generated entries
    # (MAINTENANCE_PAYMENT/EXPENSE_BILL/ADJUSTMENT), which predate this
    # catalog and have their own title-generation logic untouched.
    heading_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account_headings.id"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_edited: Mapped[bool] = mapped_column(nullable=False, default=False)
    last_edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    related_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True
    )
    related_expense_bill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expense_bills.id"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    __table_args__ = (
        # normal entries positive; ADJUSTMENT may be +/- (Section 49.10)
        CheckConstraint(
            "(source IN ('MANUAL','MAINTENANCE_PAYMENT','EXPENSE_BILL') "
            "AND amount > 0) OR source = 'ADJUSTMENT'",
            name="ck_account_entries_amount_sign",
        ),
        # ADJUSTMENT is always income-side under current scope (audit precision)
        CheckConstraint(
            "source != 'ADJUSTMENT' OR entry_type = 'INCOME'",
            name="ck_account_entries_adjustment_is_income",
        ),
        # source <-> entry_type/related-field consistency (audit item P)
        CheckConstraint(
            "source != 'MAINTENANCE_PAYMENT' OR "
            "(entry_type = 'INCOME' AND related_payment_id IS NOT NULL "
            "AND related_expense_bill_id IS NULL)",
            name="ck_account_entries_maintenance_payment_shape",
        ),
        CheckConstraint(
            "source != 'EXPENSE_BILL' OR "
            "(entry_type = 'EXPENSE' AND related_expense_bill_id IS NOT NULL "
            "AND related_payment_id IS NULL)",
            name="ck_account_entries_expense_bill_shape",
        ),
        CheckConstraint(
            "source != 'MANUAL' OR "
            "(related_payment_id IS NULL AND related_expense_bill_id IS NULL)",
            name="ck_account_entries_manual_shape",
        ),
        # ledger exactly-once (audit item F) — no duplicate postings
        Index(
            "ux_account_entries_payment_once",
            "related_payment_id",
            unique=True,
            postgresql_where="source = 'MAINTENANCE_PAYMENT'",
        ),
        Index(
            "ux_account_entries_expense_bill_once",
            "related_expense_bill_id",
            unique=True,
            postgresql_where="source = 'EXPENSE_BILL'",
        ),
        # NOTE (service-layer): source='MANUAL' -> created_by must hold ADMIN role.
        # System-generated rows (MAINTENANCE_PAYMENT/EXPENSE_BILL/ADJUSTMENT) are
        # never edited directly — their "correction" is always a new ADJUSTMENT row.
    )


class AccountEntryEditHistory(Base, UUIDPKMixin):
    __tablename__ = "account_entry_edit_history"

    account_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account_entries.id"), nullable=False
    )
    previous_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    previous_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    previous_entry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    edited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # NOTE: only source='MANUAL' account_entries are ever edited (service-level
    # rule) — a snapshot of pre-edit values is written here before each update.
