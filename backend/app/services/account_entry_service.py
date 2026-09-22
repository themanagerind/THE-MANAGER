"""
Account report service — Section 13.0 (2-column ledger), Section 13.1
(Admin-only entry, edit history + highlight).
"""
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounts import AccountEntry, AccountEntryEditHistory
from app.models.enums import EntrySource, EntryType


async def create_manual_entry(
    db: AsyncSession, society_id: uuid.UUID, created_by: uuid.UUID,
    entry_type: EntryType, title: str, description: str | None, amount: float, entry_date: date,
) -> AccountEntry:
    """Section 13.1 — only Admin can create (enforced by router's require_role);
    only MANUAL entries are ever created directly like this — system-generated
    entries (MAINTENANCE_PAYMENT/EXPENSE_BILL/ADJUSTMENT) come from their own
    flows (payment approval, expense bill approval, payment correction)."""
    entry = AccountEntry(
        society_id=society_id, entry_type=entry_type, source=EntrySource.MANUAL,
        title=title, description=description, amount=amount, entry_date=entry_date, created_by=created_by,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def get_entry(db: AsyncSession, society_id: uuid.UUID, entry_id: uuid.UUID) -> AccountEntry:
    entry = (
        await db.execute(select(AccountEntry).where(AccountEntry.id == entry_id, AccountEntry.society_id == society_id))
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account entry not found in this society")
    return entry


async def edit_manual_entry(
    db: AsyncSession, society_id: uuid.UUID, entry_id: uuid.UUID, edited_by: uuid.UUID,
    title: str | None, description: str | None, amount: float | None, entry_date: date | None,
) -> AccountEntry:
    """Section 13.1 — snapshot current values to history BEFORE updating,
    multiple edits allowed, is_edited flag drives the UI highlight."""
    entry = await get_entry(db, society_id, entry_id)
    if entry.source != EntrySource.MANUAL:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only MANUAL entries can be edited directly — system-generated entries are corrected "
            "via a new ADJUSTMENT entry instead",
        )

    db.add(
        AccountEntryEditHistory(
            account_entry_id=entry.id,
            previous_title=entry.title,
            previous_description=entry.description,
            previous_amount=entry.amount,
            previous_entry_date=entry.entry_date,
            edited_by=edited_by,
            edited_at=datetime.now(timezone.utc),
        )
    )

    if title is not None:
        entry.title = title
    if description is not None:
        entry.description = description
    if amount is not None:
        entry.amount = amount
    if entry_date is not None:
        entry.entry_date = entry_date

    entry.is_edited = True
    entry.last_edited_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(entry)
    return entry


async def list_entries(db: AsyncSession, society_id: uuid.UUID, skip: int = 0, limit: int = 20) -> tuple[list[AccountEntry], int]:
    """Section 13.1 — visible to all Residents (read-only), so no role
    filtering here; the router allows every role to call this."""
    total = (await db.execute(select(func.count()).select_from(AccountEntry).where(AccountEntry.society_id == society_id))).scalar_one()
    rows = (
        await db.execute(
            select(AccountEntry).where(AccountEntry.society_id == society_id)
            .order_by(AccountEntry.entry_date.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()
    return rows, total


async def balance_summary(db: AsyncSession, society_id: uuid.UUID) -> dict:
    """Section 13.0 — simple running totals, not double-entry accounting."""
    income = (
        await db.execute(
            select(func.coalesce(func.sum(AccountEntry.amount), 0)).where(
                AccountEntry.society_id == society_id, AccountEntry.entry_type == EntryType.INCOME
            )
        )
    ).scalar_one()
    expense = (
        await db.execute(
            select(func.coalesce(func.sum(AccountEntry.amount), 0)).where(
                AccountEntry.society_id == society_id, AccountEntry.entry_type == EntryType.EXPENSE
            )
        )
    ).scalar_one()
    return {
        "total_income": float(income),
        "total_expense": float(expense),
        "balance": float(income) - float(expense),
    }
