"""Read-only payment listing queries."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PaymentStatus
from app.models.payments import Payment, PaymentProof


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
