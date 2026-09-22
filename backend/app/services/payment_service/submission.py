"""Resident payment submission — Section 14 (payment lifecycle), Section
49.2 (one pending payment per due, active-resident authorization)."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MaintenanceDueStatus, PaymentAuditAction, PaymentMethod, PaymentStatus, Role, UserStatus
from app.models.identity import Property, PropertyResident, User, UserRole
from app.models.payments import MaintenanceDue, Payment, PaymentAuditLog, PaymentProof
from app.schemas.payment import SubmitPaymentIn
from app.services.payment_service._finalize import finalize_paid


async def _active_resident_authorized_for_property(
    db: AsyncSession, resident_id: uuid.UUID, property_id: uuid.UUID, society_id: uuid.UUID
) -> bool:
    """Section 49.2 active-resident payment authorization: resident must be
    actively linked (Owner or Tenant) to the property, hold an active
    RESIDENT role, and everything must resolve to the same society.

    Audit fix: also requires the property itself to be ACTIVE, matching
    scope_service.resident_owns_or_rents_property — this is a separate
    function (payment submission has its own extra RESIDENT-role check),
    not a caller of it, so the property-active check has to be repeated
    here rather than inherited."""
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

    prop = (
        await db.execute(
            select(Property).where(Property.id == property_id, Property.society_id == society_id)
        )
    ).scalar_one_or_none()
    if prop is None or prop.status != "ACTIVE":
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
    # Row lock: closes the race where two concurrent submissions (e.g. two
    # MOCK_ONLINE requests, which skip the PENDING_APPROVAL stage entirely
    # and go straight to PAID) both read status=PENDING before either
    # commits — the second waits here, then re-reads PAID and is rejected
    # below instead of double-crediting.
    due = (
        await db.execute(
            select(MaintenanceDue)
            .where(MaintenanceDue.id == body.maintenance_due_id, MaintenanceDue.society_id == society_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if due is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Maintenance due not found in this society")

    # Audit fix: the only existing guard was "one PENDING_APPROVAL payment
    # per due" — a due that's already PAID had no guard at all, so a
    # Resident (or a retried MOCK_ONLINE request) could submit another
    # payment against it, crediting the wallet and posting ledger income a
    # second time for the same due.
    if due.status == MaintenanceDueStatus.PAID:
        raise HTTPException(status.HTTP_409_CONFLICT, "This due is already paid")

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
        await finalize_paid(db, payment, due, approved_by=None)
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
