"""Maintenance due service — Section 13.2, plus the opt-in late-payment
penalty extension (see MaintenanceDue's penalty_* columns)."""
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MaintenanceDueStatus
from app.models.identity import Property, PropertyResident
from app.models.payments import MaintenanceDue
from app.schemas.payment import MaintenanceDueByLocationOut, MaintenanceDueOut


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


async def generate_monthly_bills(
    db: AsyncSession,
    society_id: uuid.UUID,
    occupied_amount: float,
    vacant_amount: float,
    billing_month: date,
    due_date: date,
    penalty_enabled: bool = False,
    penalty_per_day: float | None = None,
) -> list[MaintenanceDue]:
    """Admin enters TWO amounts + month -> system creates ONE bill per
    property, society-wide (Section 13.2, resolved: 1 bill per property,
    not per resident-relationship) — occupied_amount for a property with
    at least one active Owner/Tenant link, vacant_amount for everything
    else (a society routinely has some empty flats/houses, which
    typically carry a lower or zero maintenance rate).

    due_date is Admin-set, independent of billing_month. penalty_enabled
    is opt-in (defaults off); when set, penalty_per_day must be a
    positive amount — this is the ONLY combination allowed, since a
    penalty with no rate (or a rate with the feature off) is meaningless.

    Concurrency fix (audit round-8 item 9): uses a single `INSERT ... ON
    CONFLICT (society_id, property_id, billing_month) DO NOTHING` statement
    instead of read-then-insert. Two Admins clicking "generate" at the same
    moment (or a retried/duplicate request) no longer risk an IntegrityError
    aborting the whole batch — each request idempotently inserts only the
    rows that don't exist yet, atomically, in one round-trip."""
    if penalty_enabled:
        if penalty_per_day is None or penalty_per_day <= 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "penalty_per_day must be a positive amount when the penalty is enabled"
            )
    else:
        penalty_per_day = None

    month = _first_of_month(billing_month)

    properties = (
        await db.execute(
            select(Property).where(Property.society_id == society_id, Property.status == "ACTIVE")
        )
    ).scalars().all()
    if not properties:
        return []

    occupied_property_ids = set(
        (
            await db.execute(
                select(PropertyResident.property_id).where(
                    PropertyResident.society_id == society_id, PropertyResident.is_active.is_(True)
                ).distinct()
            )
        ).scalars().all()
    )

    now = datetime.now(timezone.utc)
    rows = [
        {
            "id": uuid.uuid4(),
            "society_id": society_id,
            "property_id": prop.id,
            "amount": occupied_amount if prop.id in occupied_property_ids else vacant_amount,
            "due_date": due_date,
            "status": MaintenanceDueStatus.PENDING.value,
            "billing_month": month,
            "generated_at": now,
            "updated_at": now,
            "penalty_enabled": penalty_enabled,
            "penalty_per_day": penalty_per_day,
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


async def list_outstanding_dues_by_location(
    db: AsyncSession, society_id: uuid.UUID, location_id: uuid.UUID
) -> list[MaintenanceDueByLocationOut]:
    """Every still-PENDING due for a Wing/Row's properties, one query
    instead of a Manager opening each property one at a time — the
    house_number is joined in since a Manager only sees property_id
    otherwise, and there's no per-property picker here to already know
    which flat a bare UUID belongs to."""
    rows = (
        await db.execute(
            select(MaintenanceDue, Property.house_number)
            .join(Property, Property.id == MaintenanceDue.property_id)
            .where(
                Property.society_id == society_id,
                Property.location_id == location_id,
                MaintenanceDue.status == MaintenanceDueStatus.PENDING,
            )
            .order_by(MaintenanceDue.due_date)
        )
    ).all()
    result = []
    for due, house_number in rows:
        penalty = compute_penalty(due)
        result.append(
            MaintenanceDueByLocationOut(
                id=due.id, property_id=due.property_id, property_house_number=house_number,
                billing_month=due.billing_month, amount=float(due.amount), due_date=due.due_date,
                status=due.status, penalty_amount=penalty, total_amount=float(due.amount) + penalty,
            )
        )
    return result


async def _get_due_or_404(db: AsyncSession, society_id: uuid.UUID, due_id: uuid.UUID) -> MaintenanceDue:
    due = (
        await db.execute(
            select(MaintenanceDue).where(MaintenanceDue.id == due_id, MaintenanceDue.society_id == society_id)
        )
    ).scalar_one_or_none()
    if due is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Maintenance due not found in this society")
    return due


def compute_penalty(due: MaintenanceDue, as_of: date | None = None) -> float:
    """Late-payment penalty accrued so far — computed fresh on every
    read, never stored as a running total (this app has no in-app
    scheduler to accumulate one against, same reasoning as
    upload_service's orphan-proof cleanup being a standalone cron
    instead of a background job here). Always 0 once the due is no
    longer PENDING (a fixed amount was already folded into the paying
    Payment.penalty_amount at submission time), if penalty isn't enabled
    for this due, or if an Admin has waived it."""
    if not due.penalty_enabled or due.penalty_waived or due.penalty_per_day is None:
        return 0.0
    if due.status != MaintenanceDueStatus.PENDING:
        return 0.0
    today = as_of or date.today()
    days_overdue = (today - due.due_date).days
    if days_overdue <= 0:
        return 0.0
    return round(float(due.penalty_per_day) * days_overdue, 2)


def due_out(due: MaintenanceDue) -> MaintenanceDueOut:
    penalty = compute_penalty(due)
    return MaintenanceDueOut(
        id=due.id, society_id=due.society_id, property_id=due.property_id, amount=float(due.amount),
        due_date=due.due_date, status=due.status, billing_month=due.billing_month, generated_at=due.generated_at,
        penalty_enabled=due.penalty_enabled,
        penalty_per_day=float(due.penalty_per_day) if due.penalty_per_day is not None else None,
        penalty_waived=due.penalty_waived, penalty_waived_at=due.penalty_waived_at,
        penalty_waived_by=due.penalty_waived_by, penalty_amount=penalty, total_amount=float(due.amount) + penalty,
    )


async def waive_penalty(db: AsyncSession, society_id: uuid.UUID, due_id: uuid.UUID, waived_by: uuid.UUID) -> MaintenanceDue:
    """Admin forgives an already-enabled penalty for this specific due —
    idempotent (waiving an already-waived due is a no-op, not an error)."""
    due = await _get_due_or_404(db, society_id, due_id)
    if not due.penalty_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Penalty isn't enabled for this due")
    if not due.penalty_waived:
        due.penalty_waived = True
        due.penalty_waived_at = datetime.now(timezone.utc)
        due.penalty_waived_by = waived_by
        await db.commit()
        await db.refresh(due)
    return due
