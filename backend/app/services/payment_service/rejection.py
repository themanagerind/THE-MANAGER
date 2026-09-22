"""Admin/Sub-admin rejection of a PENDING_APPROVAL payment — Section 14.
The due stays PENDING so a new payment submission is allowed (Section 49.2)."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.models.enums import PaymentAuditAction, PaymentStatus, Role
from app.models.payments import Payment, PaymentAuditLog
from app.services.scope_service import subadmin_has_scope_over_property


async def reject_payment(
    db: AsyncSession,
    society_id: uuid.UUID,
    approver: CurrentUser,
    payment_id: uuid.UUID,
    rejection_reason: str,
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

    payment.status = PaymentStatus.REJECTED
    payment.rejected_at = datetime.now(timezone.utc)
    payment.rejected_by = approver.user_id
    payment.rejection_reason = rejection_reason

    db.add(
        PaymentAuditLog(
            payment_id=payment.id,
            action=PaymentAuditAction.REJECTED,
            old_status=PaymentStatus.PENDING_APPROVAL.value,
            new_status=PaymentStatus.REJECTED.value,
            reason=rejection_reason,
            performed_by=approver.user_id,
        )
    )
    await db.commit()
    await db.refresh(payment)
    return payment
