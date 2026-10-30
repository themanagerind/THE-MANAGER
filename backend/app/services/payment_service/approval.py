"""Admin/Sub-admin approval of a PENDING_APPROVAL payment — Section 14,
with row locking (Transactions section) so a concurrent approve/reject/
correct on the same payment can never race."""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.models.enums import PaymentAuditAction, PaymentStatus, Role
from app.models.payments import MaintenanceDue, Payment, PaymentAuditLog
from app.services.payment_service._finalize import finalize_paid
from app.services.scope_service import subadmin_has_scope_over_property


async def approve_payment(
    db: AsyncSession, society_id: uuid.UUID, approver: CurrentUser, payment_id: uuid.UUID
) -> Payment:
    payment = (
        await db.execute(
            select(Payment).where(Payment.id == payment_id, Payment.society_id == society_id).with_for_update()
        )
    ).scalar_one_or_none()
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found in this society")
    if payment.status != PaymentStatus.PENDING_APPROVAL:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Payment is already {payment.status.value}")

    if approver.active_role == Role.SUB_ADMIN and not await subadmin_has_scope_over_property(
        db, approver.user_id, payment.property_id, society_id
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Payment's property is outside your assigned scope")

    due = (
        await db.execute(
            select(MaintenanceDue).where(MaintenanceDue.id == payment.maintenance_due_id).with_for_update()
        )
    ).scalar_one_or_none()

    await finalize_paid(db, payment, due, approved_by=approver.user_id)
    db.add(
        PaymentAuditLog(
            payment_id=payment.id,
            action=PaymentAuditAction.APPROVED,
            old_status=PaymentStatus.PENDING_APPROVAL.value,
            new_status=PaymentStatus.PAID.value,
            performed_by=approver.user_id,
        )
    )
    await db.commit()
    await db.refresh(payment)
    return payment
