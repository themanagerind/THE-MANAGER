"""Payment/wallet schemas — Section 13.2, 14, 15."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import (
    MaintenanceDueStatus,
    PaymentMethod,
    PaymentStatus,
    ProofType,
)


class GenerateMonthlyBillsIn(BaseModel):
    """Section 13.2 — Admin one-click monthly bill generation: two
    amounts (a society always has some vacant flats/houses alongside
    occupied ones) + month -> one bill per property, society-wide.
    "Occupied" means the property has at least one active Owner/Tenant
    link (property_residents.is_active) at generation time; everything
    else gets the vacant amount.

    due_date is explicit, separate from billing_month — Admin decides
    the actual payment deadline. penalty_enabled is an opt-in checkbox
    (never on by default); when true, penalty_per_day (required in that
    case, validated service-side since Pydantic alone can't express
    "required only if this other field is true") is added per day once
    due_date has passed, on top of the base amount, until paid or an
    Admin waives it (see MaintenanceDue.penalty_waived)."""

    occupied_amount: float
    vacant_amount: float
    billing_month: date  # any date within the month; normalized to 1st
    due_date: date
    penalty_enabled: bool = False
    penalty_per_day: float | None = None


class MaintenanceDueOut(BaseModel):
    """Not built via model_validate — penalty_amount/total_amount are
    computed on read (maintenance_service.compute_penalty), not columns;
    see maintenance_service.due_out, same "constructed as a plain dict/
    object" pattern as admin_change_service._as_dict."""

    id: uuid.UUID
    society_id: uuid.UUID
    property_id: uuid.UUID
    amount: float
    due_date: date
    status: MaintenanceDueStatus
    billing_month: date
    generated_at: datetime
    penalty_enabled: bool
    penalty_per_day: float | None
    penalty_waived: bool
    # Who waived it and when — the audit trail for an Admin's "forgive
    # this penalty" decision, same "who/when" shape as every other
    # override in this app (Payment.approved_by/rejected_by, etc.).
    penalty_waived_at: datetime | None
    penalty_waived_by: uuid.UUID | None
    # Accrued as of now — 0 if penalty isn't enabled/waived/not yet overdue.
    penalty_amount: float
    # amount + penalty_amount, for display convenience.
    total_amount: float


class SubmitPaymentIn(BaseModel):
    maintenance_due_id: uuid.UUID
    payment_method: PaymentMethod
    reference_number: str | None = None
    idempotency_key: uuid.UUID
    # for MANUAL_UPI/MANUAL_CASH — at least one proof required (Section 14.2/14.3)
    proof_type: ProofType | None = None
    proof_file_url: str | None = None


class PaymentOut(BaseModel):
    """Not built via model_validate — resident_name/property_house_number
    are joined in, not columns on Payment; see payment_service.payment_out,
    same "constructed as a plain object" pattern as maintenance_service.due_out."""

    id: uuid.UUID
    society_id: uuid.UUID
    maintenance_due_id: uuid.UUID
    property_id: uuid.UUID
    resident_id: uuid.UUID
    # Who's paying and which property — without these, an Admin/Sub-admin
    # approving a payment could only see raw UUIDs and had no way to tell
    # who the pending approval actually belonged to.
    resident_name: str
    property_house_number: str
    payment_method: PaymentMethod
    amount: float
    # How much of `amount` was a late-payment penalty (0 if none accrued).
    penalty_amount: float
    status: PaymentStatus
    reference_number: str | None
    paid_marked_at: datetime | None
    approved_at: datetime | None
    approved_by: uuid.UUID | None
    rejected_at: datetime | None
    rejected_by: uuid.UUID | None
    rejection_reason: str | None
    created_at: datetime


class PaymentProofOut(BaseModel):
    id: uuid.UUID
    payment_id: uuid.UUID
    proof_type: ProofType
    file_url: str
    uploaded_at: datetime
    uploaded_by: uuid.UUID

    model_config = {"from_attributes": True}


class UploadProofOut(BaseModel):
    file_url: str


class RejectPaymentIn(BaseModel):
    rejection_reason: str


class CorrectPaymentIn(BaseModel):
    new_amount: float
    reason: str


class WalletOut(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    balance: float

    model_config = {"from_attributes": True}
