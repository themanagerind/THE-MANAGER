"""Read-only payment listing queries."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PaymentStatus
from app.models.identity import Property, User
from app.models.payments import Payment, PaymentProof
from app.schemas.payment import PaymentOut


async def list_payments_for_society(
    db: AsyncSession, society_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> tuple[list[Payment], int]:
    total = (
        await db.execute(select(func.count()).select_from(Payment).where(Payment.society_id == society_id))
    ).scalar_one()
    rows = (
        await db.execute(
            select(Payment).where(Payment.society_id == society_id).order_by(Payment.created_at.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()
    return rows, total


async def list_pending_payments(db: AsyncSession, society_id: uuid.UUID) -> list[Payment]:
    return (
        await db.execute(
            select(Payment).where(Payment.society_id == society_id, Payment.status == PaymentStatus.PENDING_APPROVAL)
        )
    ).scalars().all()


async def list_all_payments_for_society(db: AsyncSession, society_id: uuid.UUID) -> list[Payment]:
    """Unpaginated — used when the caller (Sub-admin) needs to filter by
    scope before paginating, since filtering after an offset/limit slice
    would silently return short pages and a wrong total."""
    return (
        await db.execute(
            select(Payment).where(Payment.society_id == society_id).order_by(Payment.created_at.desc())
        )
    ).scalars().all()


async def get_payment(db: AsyncSession, society_id: uuid.UUID, payment_id: uuid.UUID) -> Payment | None:
    return (
        await db.execute(select(Payment).where(Payment.id == payment_id, Payment.society_id == society_id))
    ).scalar_one_or_none()


async def list_proofs_for_payment(db: AsyncSession, payment_id: uuid.UUID) -> list[PaymentProof]:
    return (
        await db.execute(select(PaymentProof).where(PaymentProof.payment_id == payment_id))
    ).scalars().all()


async def payment_out_list(db: AsyncSession, payments: list[Payment]) -> list[PaymentOut]:
    """Bulk-resolves resident_name/property_house_number for a whole page
    of payments in two queries (not one per payment) — an Admin/Sub-admin
    approving payments previously only saw the raw amount/method/reference,
    with no way to tell whose payment it was."""
    if not payments:
        return []
    resident_ids = {p.resident_id for p in payments}
    property_ids = {p.property_id for p in payments}
    names = dict(
        (await db.execute(select(User.id, User.full_name).where(User.id.in_(resident_ids)))).all()
    )
    house_numbers = dict(
        (await db.execute(select(Property.id, Property.house_number).where(Property.id.in_(property_ids)))).all()
    )
    return [
        PaymentOut(
            id=p.id, society_id=p.society_id, maintenance_due_id=p.maintenance_due_id,
            property_id=p.property_id, resident_id=p.resident_id,
            resident_name=names.get(p.resident_id, "Unknown"),
            property_house_number=house_numbers.get(p.property_id, "—"),
            payment_method=p.payment_method, amount=float(p.amount), penalty_amount=float(p.penalty_amount),
            status=p.status, reference_number=p.reference_number, paid_marked_at=p.paid_marked_at,
            approved_at=p.approved_at, approved_by=p.approved_by, rejected_at=p.rejected_at,
            rejected_by=p.rejected_by, rejection_reason=p.rejection_reason, created_at=p.created_at,
        )
        for p in payments
    ]


async def payment_out(db: AsyncSession, payment: Payment) -> PaymentOut:
    return (await payment_out_list(db, [payment]))[0]
