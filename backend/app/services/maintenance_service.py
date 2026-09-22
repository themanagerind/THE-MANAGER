"""Maintenance due service — Section 13.2."""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MaintenanceDueStatus
from app.models.identity import Property
from app.models.payments import MaintenanceDue


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


async def generate_monthly_bills(
    db: AsyncSession, society_id: uuid.UUID, amount: float, billing_month: date
) -> list[MaintenanceDue]:
    """Admin enters ONE amount + month -> system creates ONE bill per
    property, society-wide (Section 13.2, resolved: 1 bill per property,
    not per resident-relationship).

    Concurrency fix (audit round-8 item 9): uses a single `INSERT ... ON
    CONFLICT (society_id, property_id, billing_month) DO NOTHING` statement
    instead of read-then-insert. Two Admins clicking "generate" at the same
    moment (or a retried/duplicate request) no longer risk an IntegrityError
    aborting the whole batch — each request idempotently inserts only the
    rows that don't exist yet, atomically, in one round-trip."""
    month = _first_of_month(billing_month)

    properties = (
        await db.execute(
            select(Property).where(Property.society_id == society_id, Property.status == "ACTIVE")
        )
    ).scalars().all()
    if not properties:
        return []

    now = datetime.now(timezone.utc)
    rows = [
        {
            "id": uuid.uuid4(),
            "society_id": society_id,
            "property_id": prop.id,
            "amount": amount,
            "due_date": month,
            "status": MaintenanceDueStatus.PENDING.value,
            "billing_month": month,
            "generated_at": now,
            "updated_at": now,
        }
        for prop in properties
    ]

    stmt = pg_insert(MaintenanceDue).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["society_id", "property_id", "billing_month"]
    ).returning(MaintenanceDue)
    result = await db.execute(stmt)
    created = result.scalars().all()
    await db.commit()
    return list(created)


async def list_dues_for_property(
    db: AsyncSession, society_id: uuid.UUID, property_id: uuid.UUID
) -> list[MaintenanceDue]:
    return (
        await db.execute(
            select(MaintenanceDue).where(
                MaintenanceDue.society_id == society_id, MaintenanceDue.property_id == property_id
            )
        )
    ).scalars().all()


async def list_dues_for_society(db: AsyncSession, society_id: uuid.UUID) -> list[MaintenanceDue]:
    return (
        await db.execute(select(MaintenanceDue).where(MaintenanceDue.society_id == society_id))
    ).scalars().all()
