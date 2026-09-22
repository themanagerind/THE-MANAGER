"""Payments/maintenance-dues/wallet endpoints."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.pagination import Page, Pagination, pagination_params
from app.schemas.payment import (
    CorrectPaymentIn,
    GenerateMonthlyBillsIn,
    MaintenanceDueOut,
    PaymentOut,
    RejectPaymentIn,
    SubmitPaymentIn,
    WalletOut,
)
from app.services import maintenance_service, payment_service, wallet_service
from app.services.scope_service import resident_owns_or_rents_property

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/maintenance-dues/generate", response_model=list[MaintenanceDueOut])
async def generate_bills(
    body: GenerateMonthlyBillsIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> list[MaintenanceDueOut]:
    """Section 13.2 — Admin one-click monthly generation."""
    dues = await maintenance_service.generate_monthly_bills(
        db, current.society_id, body.amount, body.billing_month
    )
    return [MaintenanceDueOut.model_validate(d) for d in dues]


@router.get("/maintenance-dues", response_model=list[MaintenanceDueOut])
async def list_dues(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN))],
) -> list[MaintenanceDueOut]:
    dues = await maintenance_service.list_dues_for_society(db, current.society_id)
    return [MaintenanceDueOut.model_validate(d) for d in dues]


@router.get("/maintenance-dues/by-property/{property_id}", response_model=list[MaintenanceDueOut])
async def list_dues_for_property(
    property_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[
        CurrentUser,
        Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.MANAGER, Role.RESIDENT)),
    ],
) -> list[MaintenanceDueOut]:
    # Audit finding C5/C6: Manager gets view-only access here per the
    # finalized requirement (property-level dues, no write access — Manager
    # has no route to generate/correct/reject payments anywhere in this
    # router). CRITICAL fix (audit finding C2): a Resident could previously
    # name ANY property in their own society and read its dues, not just one
    # they're linked to — same ownership check already used for
    # complaints/visitors/amenities. Admin/Sub-admin/Manager are exempt:
    # they legitimately manage every property in the society.
    if current.active_role == Role.RESIDENT and not await resident_owns_or_rents_property(
        db, current.user_id, property_id, current.society_id
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You are not an active Owner/Tenant of this property"
        )
    dues = await maintenance_service.list_dues_for_property(db, current.society_id, property_id)
    return [MaintenanceDueOut.model_validate(d) for d in dues]


@router.post("", response_model=PaymentOut)
async def submit_payment(
    body: SubmitPaymentIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> PaymentOut:
    """Section 14 — Resident submits payment (mock online -> auto PAID;
    manual -> proof required -> PENDING_APPROVAL)."""
    payment = await payment_service.submit_payment(db, current.society_id, current.user_id, body)
    return PaymentOut.model_validate(payment)


@router.get("", response_model=Page[PaymentOut])
async def list_payments(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN))],
    pagination: Annotated[Pagination, Depends(pagination_params)],
) -> Page[PaymentOut]:
    """API Contract Freeze — reference paginated list endpoint: ?skip=&limit=,
    Page[T] envelope. Apply this same shape when extending pagination to
    other list endpoints (see docs/API_CONTRACT.md)."""
    payments, total = await payment_service.list_payments_for_society(
        db, current.society_id, pagination.skip, pagination.limit
    )
    return Page(
        items=[PaymentOut.model_validate(p) for p in payments],
        total=total, skip=pagination.skip, limit=pagination.limit,
    )


@router.get("/pending", response_model=list[PaymentOut])
async def list_pending(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN))],
) -> list[PaymentOut]:
    payments = await payment_service.list_pending_payments(db, current.society_id)
    return [PaymentOut.model_validate(p) for p in payments]


@router.post("/{payment_id}/approve", response_model=PaymentOut)
async def approve(
    payment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN))],
) -> PaymentOut:
    """Sub-admin: own scope only (checked inside the service against current
    sub_admin_scopes — Section 27). Admin: any scope."""
    payment = await payment_service.approve_payment(db, current.society_id, current, payment_id)
    return PaymentOut.model_validate(payment)


@router.post("/{payment_id}/reject", response_model=PaymentOut)
async def reject(
    payment_id: uuid.UUID,
    body: RejectPaymentIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN))],
) -> PaymentOut:
    payment = await payment_service.reject_payment(
        db, current.society_id, current, payment_id, body.rejection_reason
    )
    return PaymentOut.model_validate(payment)


@router.post("/{payment_id}/correct")
async def correct(
    payment_id: uuid.UUID,
    body: CorrectPaymentIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN))],
):
    """Section 13.3/49.3 — correction event, never overwrites history."""
    correction = await payment_service.correct_payment(
        db, current.society_id, current, payment_id, body.new_amount, body.reason
    )
    return {
        "correction_id": correction.id,
        "payment_id": correction.payment_id,
        "old_amount": float(correction.old_amount),
        "new_amount": float(correction.new_amount),
        "difference": float(correction.difference),
    }


@router.get("/wallet/me", response_model=WalletOut)
async def my_wallet(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> WalletOut:
    wallet = await wallet_service.get_wallet(db, current.user_id)
    return WalletOut.model_validate(wallet)
