"""Payments/maintenance-dues/wallet endpoints."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.models.payments import Payment
from app.schemas.pagination import Page, Pagination, pagination_params
from app.schemas.payment import (
    CorrectPaymentIn,
    GenerateMonthlyBillsIn,
    MaintenanceDueOut,
    PaymentOut,
    PaymentProofOut,
    RejectPaymentIn,
    SubmitPaymentIn,
    WalletOut,
)
from app.services import maintenance_service, payment_service, upload_service, wallet_service
from app.services.scope_service import resident_owns_or_rents_property, subadmin_has_scope_over_property

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/maintenance-dues/generate", response_model=list[MaintenanceDueOut])
async def generate_bills(
    body: GenerateMonthlyBillsIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> list[MaintenanceDueOut]:
    """Section 13.2 — Admin one-click monthly generation."""
    dues = await maintenance_service.generate_monthly_bills(
        db, current.society_id, body.occupied_amount, body.vacant_amount, body.billing_month,
        body.due_date, body.penalty_enabled, body.penalty_per_day,
    )
    return [maintenance_service.due_out(d) for d in dues]


@router.get("/maintenance-dues", response_model=list[MaintenanceDueOut])
async def list_dues(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN))],
) -> list[MaintenanceDueOut]:
    dues = await maintenance_service.list_dues_for_society(db, current.society_id)
    # Audit fix: this listed every due in the society regardless of caller
    # role — a Sub-admin's Wing/Row scope (Section 27) was never applied,
    # so they could read maintenance dues (amount, status, resident/property
    # linkage) outside their assigned scope. Same pattern already used for
    # complaints (complaint_service.filter_by_subadmin_scope).
    if current.active_role == Role.SUB_ADMIN:
        dues = [
            d for d in dues
            if await subadmin_has_scope_over_property(db, current.user_id, d.property_id, current.society_id)
        ]
    return [maintenance_service.due_out(d) for d in dues]


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
    return [maintenance_service.due_out(d) for d in dues]


@router.post("/maintenance-dues/{due_id}/waive-penalty", response_model=MaintenanceDueOut)
async def waive_penalty(
    due_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> MaintenanceDueOut:
    """Admin forgives an already-enabled penalty on this due — idempotent,
    and irreversible from here (there's no "re-enable" — same "explicit
    exception, not a toggle" shape as other one-way admin overrides in
    this app)."""
    due = await maintenance_service.waive_penalty(db, current.society_id, due_id, current.user_id)
    return maintenance_service.due_out(due)


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
    if current.active_role == Role.SUB_ADMIN:
        # Audit fix: scope filtering has to happen BEFORE pagination — doing
        # it after the SQL offset/limit slice would silently return short
        # pages and a `total` that counts the whole society, not the
        # Sub-admin's scope.
        all_payments = await payment_service.list_all_payments_for_society(db, current.society_id)
        scoped = [
            p for p in all_payments
            if await subadmin_has_scope_over_property(db, current.user_id, p.property_id, current.society_id)
        ]
        total = len(scoped)
        payments = scoped[pagination.skip : pagination.skip + pagination.limit]
    else:
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
    if current.active_role == Role.SUB_ADMIN:
        payments = [
            p for p in payments
            if await subadmin_has_scope_over_property(db, current.user_id, p.property_id, current.society_id)
        ]
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


async def _authorize_proof_access(
    db: AsyncSession, current: CurrentUser, payment_id: uuid.UUID
) -> Payment:
    """Shared by both proof endpoints below — a Resident may only reach
    proofs for their own payment; Sub-admin is scope-restricted like every
    other payment endpoint; Admin has full access."""
    payment = await payment_service.get_payment(db, current.society_id, payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found in this society")

    if current.active_role == Role.RESIDENT and payment.resident_id != current.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only view proofs for your own payments")
    if current.active_role == Role.SUB_ADMIN and not await subadmin_has_scope_over_property(
        db, current.user_id, payment.property_id, current.society_id
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Payment's property is outside your assigned scope")
    return payment


@router.get("/{payment_id}/proofs", response_model=list[PaymentProofOut])
async def list_proofs(
    payment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[
        CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.RESIDENT))
    ],
) -> list[PaymentProofOut]:
    """Audit fix: this endpoint didn't exist at all — the frontend has
    called it since payment proof upload was added, but nothing backed it."""
    await _authorize_proof_access(db, current, payment_id)
    proofs = await payment_service.list_proofs_for_payment(db, payment_id)
    # Audit fix: file_url used to be the raw on-disk storage key, served
    # back by a public StaticFiles mount — no authentication needed to
    # read someone else's payment screenshot/receipt. It's now the
    # authenticated endpoint below; the storage key itself is never
    # exposed to the client.
    return [
        PaymentProofOut(
            id=p.id, payment_id=p.payment_id, proof_type=p.proof_type,
            file_url=f"/payments/{payment_id}/proofs/{p.id}/file",
            uploaded_at=p.uploaded_at, uploaded_by=p.uploaded_by,
        )
        for p in proofs
    ]


@router.get("/{payment_id}/proofs/{proof_id}/file")
async def get_proof_file(
    payment_id: uuid.UUID,
    proof_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[
        CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.RESIDENT))
    ],
) -> FileResponse:
    """The only way to read a payment-proof file's bytes — same
    authorization as list_proofs above, checked fresh on every request."""
    await _authorize_proof_access(db, current, payment_id)
    proofs = await payment_service.list_proofs_for_payment(db, payment_id)
    proof = next((p for p in proofs if p.id == proof_id), None)
    if proof is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proof not found for this payment")
    path = upload_service.resolve_payment_proof_path(proof.file_url)
    return FileResponse(path)


@router.get("/wallet/me", response_model=WalletOut)
async def my_wallet(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> WalletOut:
    wallet = await wallet_service.get_wallet(db, current.user_id)
    return WalletOut.model_validate(wallet)
