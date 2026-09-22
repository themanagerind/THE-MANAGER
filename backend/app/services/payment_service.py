"""
Payment service — Section 14 (payment lifecycle), Section 49.2 (one pending
payment per due), Section 6 (atomic payment->wallet->ledger chain),
Section 13.3/49.3 (correction event model).
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    MaintenanceDueStatus,
    PaymentAuditAction,
    PaymentMethod,
    PaymentStatus,
    Role,
    UserStatus,
)
from app.core.security import CurrentUser
from app.models.identity import PropertyResident, User, UserRole
from app.models.payments import MaintenanceDue, Payment, PaymentAuditLog, PaymentCorrection, PaymentProof
from app.schemas.payment import SubmitPaymentIn
from app.services import ledger_service, wallet_service
from app.services.scope_service import subadmin_has_scope_over_property


async def _active_resident_authorized_for_property(
    db: AsyncSession, resident_id: uuid.UUID, property_id: uuid.UUID, society_id: uuid.UUID
) -> bool:
    """Section 49.2 active-resident payment authorization: resident must be
    actively linked (Owner or Tenant) to the property, hold an active
    RESIDENT role, and everything must resolve to the same society."""
    resident = (
        await db.execute(
            select(User).where(
                User.id == resident_id, User.society_id == society_id, User.status == UserStatus.ACTIVE
            )
        )
    ).scalar_one_or_none()
    if resident is None:
        return False

    has_role = (
        await db.execute(
            select(UserRole).where(
                UserRole.user_id == resident_id, UserRole.role == Role.RESIDENT, UserRole.revoked_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if has_role is None:
        return False

    link = (
        await db.execute(
            select(PropertyResident).where(
                PropertyResident.resident_id == resident_id,
                PropertyResident.property_id == property_id,
                PropertyResident.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    return link is not None


async def submit_payment(
    db: AsyncSession, society_id: uuid.UUID, resident_id: uuid.UUID, body: SubmitPaymentIn
) -> Payment:
    due = (
        await db.execute(
            select(MaintenanceDue).where(
                MaintenanceDue.id == body.maintenance_due_id, MaintenanceDue.society_id == society_id
            )
        )
    ).scalar_one_or_none()
    if due is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Maintenance due not found in this society")

    if not await _active_resident_authorized_for_property(db, resident_id, due.property_id, society_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Resident is not actively linked to this property, or has no active Resident role",
        )

    # Section 49.2: at most one PENDING_APPROVAL payment per due — pre-check
    # for a clear error message (the DB partial unique index is the real
    # guarantee against races).
    pending = (
        await db.execute(
            select(Payment).where(
                Payment.maintenance_due_id == due.id, Payment.status == PaymentStatus.PENDING_APPROVAL
            )
        )
    ).scalar_one_or_none()
    if pending is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This due already has a payment pending approval"
        )

    is_manual = body.payment_method in (PaymentMethod.MANUAL_UPI, PaymentMethod.MANUAL_CASH)
    if is_manual and (body.proof_type is None or not body.proof_file_url):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Manual UPI/Cash payments require proof (screenshot or receipt photo) — Section 14.2/14.3",
        )

    now = datetime.now(timezone.utc)
    payment = Payment(
        society_id=society_id,
        maintenance_due_id=due.id,
        property_id=due.property_id,
        resident_id=resident_id,
        payment_method=body.payment_method,
        amount=due.amount,
        status=(
            PaymentStatus.PAID if body.payment_method == PaymentMethod.MOCK_ONLINE
            else PaymentStatus.PENDING_APPROVAL
        ),
        reference_number=body.reference_number,
        idempotency_key=body.idempotency_key,
        paid_marked_at=now,
    )
    db.add(payment)

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Duplicate submission (idempotency key already used for this due) "
            "or another payment is already pending for this due",
        ) from exc

    db.add(
        PaymentAuditLog(
            payment_id=payment.id,
            action=PaymentAuditAction.CREATED,
            new_status=payment.status.value,
            new_amount=payment.amount,
            performed_by=resident_id,
        )
    )

    if is_manual:
        db.add(
            PaymentProof(
                payment_id=payment.id,
                proof_type=body.proof_type,
                file_url=body.proof_file_url,
                uploaded_at=now,
                uploaded_by=resident_id,
            )
        )

    if body.payment_method == PaymentMethod.MOCK_ONLINE:
        # Section 14.1: auto PAID, no manual approval -> immediately run the
        # same atomic due->wallet->ledger chain as a manual approval would.
        await _finalize_paid(db, payment, due, approved_by=None)
        db.add(
            PaymentAuditLog(
                payment_id=payment.id,
                action=PaymentAuditAction.PAID_MARKED,
                old_status=PaymentStatus.PENDING_APPROVAL.value,
                new_status=PaymentStatus.PAID.value,
                performed_by=resident_id,
            )
        )

    await db.commit()
    await db.refresh(payment)
    return payment


async def _finalize_paid(
    db: AsyncSession, payment: Payment, due: MaintenanceDue, approved_by: uuid.UUID | None
) -> None:
    """The atomic due -> wallet-credit -> ledger-entry chain (Section 6).
    Caller commits — this only flushes within the caller's transaction."""
    due.status = MaintenanceDueStatus.PAID
    payment.status = PaymentStatus.PAID
    if approved_by is not None:
        payment.approved_at = datetime.now(timezone.utc)
        payment.approved_by = approved_by

    await wallet_service.credit_maintenance_payment(db, payment.resident_id, payment.id, float(payment.amount))
    await ledger_service.post_maintenance_income(
        db, payment.society_id, payment.id, float(payment.amount), created_by=approved_by or payment.resident_id
    )


async def approve_payment(
    db: AsyncSession, society_id: uuid.UUID, approver: CurrentUser, payment_id: uuid.UUID
) -> Payment:
    # Row lock (Section: Transactions — payment approval locking) prevents a
    # concurrent approve/reject/correct on the same payment from racing.
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

    await _finalize_paid(db, payment, due, approved_by=approver.user_id)
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
    # due stays PENDING -> a new payment submission is allowed (Section 49.2)

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


async def correct_payment(
    db: AsyncSession,
    society_id: uuid.UUID,
    corrector: CurrentUser,
    payment_id: uuid.UUID,
    new_amount: float,
    reason: str,
) -> PaymentCorrection:
    """Section 13.3/49.3 — never overwrites the original payment; creates a
    correction event + linked wallet/ledger ADJUSTMENT rows, all atomic.
    Rejects outright if it would drive the wallet balance negative
    (Section 13.3 RESOLVED)."""
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


async def list_payments_for_society(
    db: AsyncSession, society_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> tuple[list[Payment], int]:
    from sqlalchemy import func

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
