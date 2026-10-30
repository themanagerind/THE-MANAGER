"""Wallet redemption schemas — Resident -> Platform Owner Master Wallet
point transfer (user-requested), and the code a future Ecom store's
backend verifies."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RedemptionCreateIn(BaseModel):
    amount: float = Field(gt=0)


class RedemptionCodeOut(BaseModel):
    id: uuid.UUID
    code: str
    amount: float
    is_used: bool
    used_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RedemptionVerifyIn(BaseModel):
    code: str
    # Store's own idempotency key for this redemption attempt (any stable
    # string the store generates per attempt, e.g. its own order/txn id).
    # Retrying with the SAME request_id replays the original success
    # instead of a 409 if the first response never reached the store —
    # see wallet_service.verify_and_redeem_code. Optional for backward
    # compatibility, but a store that skips it loses idempotent retries.
    request_id: str | None = Field(default=None, max_length=100)


class RedemptionVerifyOut(BaseModel):
    # Smallest currency unit (paise for INR), never a float rupee amount —
    # user-reported: floats crossing a system boundary as money is a
    # precision-bug class best avoided entirely rather than guarded against.
    amount_paise: int
    used_at: datetime
