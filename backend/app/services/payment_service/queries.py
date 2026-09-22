"""Read-only payment listing queries."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PaymentStatus
from app.models.payments import Payment


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
