"""Visitor service — Section 18, transitions per Section 49.13."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import VisitorStatus
from app.models.identity import Property
from app.models.operations import Visitor, VisitorLog
from app.services.scope_service import resident_owns_or_rents_property

# Section 49.13 — allowed transitions.
_ALLOWED_TRANSITIONS: dict[VisitorStatus, set[VisitorStatus]] = {
    VisitorStatus.PRE_APPROVED: {VisitorStatus.EXPECTED, VisitorStatus.ENTERED, VisitorStatus.CANCELLED},
    VisitorStatus.EXPECTED: {VisitorStatus.ENTERED, VisitorStatus.CANCELLED},
    VisitorStatus.ENTERED: {VisitorStatus.EXITED},
    VisitorStatus.EXITED: set(),
    VisitorStatus.CANCELLED: set(),
}


async def pre_approve(
    db: AsyncSession, society_id: uuid.UUID, resident_id: uuid.UUID, property_id: uuid.UUID,
    visitor_name: str, visitor_mobile: str | None, visit_date, purpose: str | None,
) -> Visitor:
    # CRITICAL fix (audit round-8): a Resident could previously pre-approve
    # a visitor against ANY property in their society, not just their own.
    if not await resident_owns_or_rents_property(db, resident_id, property_id, society_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You are not an active Owner/Tenant of this property"
        )

    visitor = Visitor(
        society_id=society_id, property_id=property_id, resident_id=resident_id,
        visitor_name=visitor_name, visitor_mobile=visitor_mobile, visit_date=visit_date,
        status=VisitorStatus.PRE_APPROVED, purpose=purpose,
    )
    db.add(visitor)
    await db.commit()
    await db.refresh(visitor)
    return visitor


async def get_visitor(db: AsyncSession, society_id: uuid.UUID, visitor_id: uuid.UUID) -> Visitor:
    visitor = (
        await db.execute(select(Visitor).where(Visitor.id == visitor_id, Visitor.society_id == society_id))
    ).scalar_one_or_none()
    if visitor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Visitor not found in this society")
    return visitor


async def _transition(db: AsyncSession, visitor: Visitor, new_status: VisitorStatus) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(visitor.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot transition visitor from {visitor.status.value} to {new_status.value}",
        )
    visitor.status = new_status


async def resident_update_status(
    db: AsyncSession, society_id: uuid.UUID, resident_id: uuid.UUID, visitor_id: uuid.UUID, new_status: VisitorStatus
) -> Visitor:
    """PRE_APPROVED/EXPECTED/CANCELLED are Resident actions (Section 49.13).
    HIGH fix (audit round-8): must also verify this visitor belongs to the
    calling Resident — previously any Resident in the society could modify
    any other Resident's visitor."""
    if new_status not in (VisitorStatus.EXPECTED, VisitorStatus.CANCELLED):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Residents can only set EXPECTED or CANCELLED")
    visitor = await get_visitor(db, society_id, visitor_id)
    if visitor.resident_id != resident_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This visitor was not pre-approved by you")
    await _transition(db, visitor, new_status)
    await db.commit()
    await db.refresh(visitor)
    return visitor


async def guard_mark_entry(
    db: AsyncSession, society_id: uuid.UUID, visitor_id: uuid.UUID, guard_id: uuid.UUID
) -> Visitor:
    visitor = await get_visitor(db, society_id, visitor_id)
    await _transition(db, visitor, VisitorStatus.ENTERED)
    db.add(VisitorLog(visitor_id=visitor.id, guard_id=guard_id, entry_at=datetime.now(timezone.utc)))
    await db.commit()
    await db.refresh(visitor)
    return visitor


async def guard_mark_exit(
    db: AsyncSession, society_id: uuid.UUID, visitor_id: uuid.UUID, guard_id: uuid.UUID
) -> Visitor:
    visitor = await get_visitor(db, society_id, visitor_id)
    await _transition(db, visitor, VisitorStatus.EXITED)

    log = (
        await db.execute(
            select(VisitorLog).where(VisitorLog.visitor_id == visitor.id, VisitorLog.exit_at.is_(None))
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if log is not None:
        log.exit_at = now
    else:
        db.add(VisitorLog(visitor_id=visitor.id, guard_id=guard_id, exit_at=now))

    await db.commit()
    await db.refresh(visitor)
    return visitor


async def list_visitors_for_resident(db: AsyncSession, society_id: uuid.UUID, resident_id: uuid.UUID, skip: int = 0, limit: int = 20) -> tuple[list[Visitor], int]:
    from sqlalchemy import func
    total = (
        await db.execute(
            select(func.count()).select_from(Visitor)
            .where(Visitor.society_id == society_id, Visitor.resident_id == resident_id)
        )
    ).scalar_one()
    rows = (
        await db.execute(
            select(Visitor).where(Visitor.society_id == society_id, Visitor.resident_id == resident_id)
            .order_by(Visitor.visit_date.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()
    return rows, total


async def list_visitors_for_society(
    db: AsyncSession, society_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> tuple[list[Visitor], int]:
    """Admin/Sub-admin view — full VisitorOut (unlike the Guard's
    restricted projection above), paginated. Sub-admin scope filtering
    happens at the API layer, same pattern as payments/dues/residents."""
    from sqlalchemy import func

    total = (
        await db.execute(select(func.count()).select_from(Visitor).where(Visitor.society_id == society_id))
    ).scalar_one()
    rows = (
        await db.execute(
            select(Visitor).where(Visitor.society_id == society_id)
            .order_by(Visitor.visit_date.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()
    return rows, total


async def list_all_visitors_for_society(db: AsyncSession, society_id: uuid.UUID) -> list[Visitor]:
    """Unpaginated — used when the caller (Sub-admin) needs to filter by
    scope before paginating, same reasoning as
    payment_service.list_all_payments_for_society."""
    return (
        await db.execute(
            select(Visitor).where(Visitor.society_id == society_id).order_by(Visitor.visit_date.desc())
        )
    ).scalars().all()


async def list_visitors_for_guard(db: AsyncSession, society_id: uuid.UUID) -> list[tuple[Visitor, str]]:
    """Section 21 data boundary — returns (visitor, property_house_number)
    pairs only; the router projects this into GuardVisitorOut, never
    exposing resident/payment/wallet data."""
    rows = (
        await db.execute(
            select(Visitor, Property.house_number)
            .join(Property, Property.id == Visitor.property_id)
            .where(Visitor.society_id == society_id)
        )
    ).all()
    return [(v, house_number) for v, house_number in rows]
