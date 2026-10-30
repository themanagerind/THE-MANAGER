"""Post-payment amount correction — Section 13.3/49.3. Never overwrites the
original payment; creates a correction event + linked wallet/ledger
ADJUSTMENT rows, all atomic. Rejects outright if it would drive the
wallet balance negative (Section 13.3 RESOLVED)."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.models.enums import PaymentAuditAction, PaymentStatus, Role
from app.models.payments import Payment, PaymentAuditLog, PaymentCorrection
from app.services import ledger_service, wallet_service
from app.services.scope_service import subadmin_has_scope_over_property


async def correct_payment(
    db: AsyncSession,
    society_id: uuid.UUID,
    corrector: CurrentUser,
    payment_id: uuid.UUID,
    new_amount: float,
    reason: str,
) -> PaymentCorrection:
    payment = (
        await db.execute(
            select(Payment).where(Payment.id == payment_id, Payment.society_id == society_id).with_for_update()
        )
    ).scalar_one_or_none()
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found in this society")
    if payment.status != PaymentStatus.PAID:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only PAID payments can be corrected")

    if corrector.active_role == Role.SUB_ADMIN and not await subadmin_has_scope_over_property(
        db, corrector.user_id, payment.property_id, society_id
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Payment's property is outside your assigned scope")

    old_amount = float(payment.amount)
    difference = new_amount - old_amount

    # This raises 409 (and never persists) if it would go negative —
    # wallet_service.apply_adjustment enforces this.
    wallet_txn = await wallet_service.apply_adjustment(
        db, payment.resident_id, difference, description=f"Correction on payment {payment.id}"
    )
    ledger_entry = await ledger_service.post_adjustment(
        db, society_id, difference, description=f"Correction on payment {payment.id}", created_by=corrector.user_id
    )

    correction = PaymentCorrection(
        payment_id=payment.id,
        old_amount=old_amount,
        new_amount=new_amount,
        difference=difference,
        reason=reason,
        corrected_by=corrector.user_id,
        corrected_at=datetime.now(timezone.utc),
        wallet_adjustment_txn_id=wallet_txn.id,
        ledger_adjustment_entry_id=ledger_entry.id,
    )
    db.add(correction)

    payment.amount = new_amount  # current-state field; history preserved via PaymentCorrection rows

    db.add(
        PaymentAuditLog(
            payment_id=payment.id,
            action=PaymentAuditAction.CORRECTED,
            old_amount=old_amount,
            new_amount=new_amount,
            reason=reason,
            performed_by=corrector.user_id,
        )
    )

    await db.commit()
    await db.refresh(correction)
    return correction
