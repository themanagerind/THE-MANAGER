"""
Ledger service — Section 13.0/13.2/13.3 (2-column Income/Expense ledger),
Section 49.10 (Adjustment entries always Income-side under current scope).
"""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounts import AccountEntry
from app.models.enums import EntrySource, EntryType


async def post_maintenance_income(
    db: AsyncSession, society_id: uuid.UUID, payment_id: uuid.UUID, amount: float, created_by: uuid.UUID
) -> AccountEntry:
    """Exactly-once per payment — relies on the partial unique index on
    (related_payment_id) WHERE source='MAINTENANCE_PAYMENT'."""
    entry = AccountEntry(
        society_id=society_id,
        entry_type=EntryType.INCOME,
        source=EntrySource.MAINTENANCE_PAYMENT,
        title="Maintenance payment received",
        amount=amount,
        entry_date=date.today(),
        related_payment_id=payment_id,
        created_by=created_by,
    )
    db.add(entry)
    await db.flush()
    return entry


async def post_adjustment(
    db: AsyncSession, society_id: uuid.UUID, difference: float, description: str, created_by: uuid.UUID
) -> AccountEntry:
    """Always entry_type=INCOME regardless of sign (Section 49.10) — only
    maintenance-payment corrections exist in scope currently."""
    entry = AccountEntry(
        society_id=society_id,
        entry_type=EntryType.INCOME,
        source=EntrySource.ADJUSTMENT,
        title="Payment correction adjustment",
        description=description,
        amount=difference,
        entry_date=date.today(),
        created_by=created_by,
    )
    db.add(entry)
    await db.flush()
    return entry


async def post_expense_bill_expense(
    db: AsyncSession, society_id: uuid.UUID, expense_bill_id: uuid.UUID, amount: float, created_by: uuid.UUID
) -> AccountEntry:
    """Exactly-once per expense bill — relies on the partial unique index
    on (related_expense_bill_id) WHERE source='EXPENSE_BILL'. Called when
    an expense bill reaches APPROVED (100% active Sub-admin approval)."""
    entry = AccountEntry(
        society_id=society_id,
        entry_type=EntryType.EXPENSE,
        source=EntrySource.EXPENSE_BILL,
        title="Approved expense bill",
        amount=amount,
        entry_date=date.today(),
        related_expense_bill_id=expense_bill_id,
        created_by=created_by,
    )
    db.add(entry)
    await db.flush()
    return entry
