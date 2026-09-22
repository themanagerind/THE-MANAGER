"""Shared atomic due -> wallet-credit -> ledger-entry chain (Section 6),
used by both submission (mock-online auto-pay) and approval (manual
payment approved by Admin/Sub-admin) — the one place this chain is
written, so both entry points stay atomic and consistent."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MaintenanceDueStatus, PaymentStatus
from app.models.payments import MaintenanceDue, Payment
from app.services import ledger_service, wallet_service


async def finalize_paid(
    db: AsyncSession, payment: Payment, due: MaintenanceDue, approved_by: UUID | None
) -> None:
    """Caller commits — this only flushes within the caller's transaction."""
    due.status = MaintenanceDueStatus.PAID
    payment.status = PaymentStatus.PAID
    if approved_by is not None:
        payment.approved_at = datetime.now(timezone.utc)
        payment.approved_by = approved_by

    await wallet_service.credit_maintenance_payment(db, payment.resident_id, payment.id, float(payment.amount))
    await ledger_service.post_maintenance_income(
        db, payment.society_id, payment.id, float(payment.amount), created_by=approved_by or payment.resident_id
    )
