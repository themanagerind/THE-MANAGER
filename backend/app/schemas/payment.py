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
    """Section 13.2 — Admin one-click monthly bill generation:
    single amount + month -> one bill per property, society-wide."""

    amount: float
    billing_month: date  # any date within the month; normalized to 1st


class MaintenanceDueOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    property_id: uuid.UUID
    amount: float
    due_date: date
    status: MaintenanceDueStatus
    billing_month: date
    generated_at: datetime

    model_config = {"from_attributes": True}


class SubmitPaymentIn(BaseModel):
    maintenance_due_id: uuid.UUID
    payment_method: PaymentMethod
    reference_number: str | None = None
    idempotency_key: uuid.UUID
    # for MANUAL_UPI/MANUAL_CASH — at least one proof required (Section 14.2/14.3)
    proof_type: ProofType | None = None
    proof_file_url: str | None = None


class PaymentOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    maintenance_due_id: uuid.UUID
    property_id: uuid.UUID
    resident_id: uuid.UUID
    payment_method: PaymentMethod
    amount: float
    status: PaymentStatus
    reference_number: str | None
    paid_marked_at: datetime | None
    approved_at: datetime | None
    approved_by: uuid.UUID | None
    rejected_at: datetime | None
    rejected_by: uuid.UUID | None
    rejection_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


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
