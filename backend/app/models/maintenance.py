from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime, timezone
import uuid

class MaintenanceBatch(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    society_id: str
    month: str  # Format: YYYY-MM
    amount_per_flat: float
    total_flats: int
    cancelled_flats: int = 0
    billed_flats: int
    total_amount: float
    generated_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FlatBill(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    batch_id: str
    flat_id: str
    flat_number: str
    wing_id: str
    wing_name: str
    resident_id: Optional[str] = None
    resident_name: Optional[str] = None
    amount: float
    month: str
    status: Literal["pending", "paid", "verified", "overdue"] = "pending"
    is_cancelled: bool = False
    cancel_reason: Optional[str] = None
    cancelled_by: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    payment_mode: Optional[str] = None
    payment_ref: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FlatBillAudit(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    flat_bill_id: str
    flat_number: str
    month: str
    action: str
    reason: Optional[str] = None
    done_by_id: str
    done_by_name: str
    done_by_role: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MaintenancePreviewRequest(BaseModel):
    month: str
    amount_per_flat: float

class MaintenanceGenerateRequest(BaseModel):
    month: str
    amount_per_flat: float
    excluded_flat_ids: List[str] = []
    cancel_reasons: dict = {}  # {flat_id: reason}

class PaymentSubmitRequest(BaseModel):
    payment_mode: Literal["cash", "upi", "bank", "cheque"]
    payment_ref: str

class PaymentVerifyRequest(BaseModel):
    action: Literal["approve", "reject"]
    reason: Optional[str] = None

class BillCancelRequest(BaseModel):
    reason: str

class MaintenancePreviewResponse(BaseModel):
    month: str
    amount_per_flat: float
    total_active_flats: int
    total_amount: float
    flats: List[dict]
