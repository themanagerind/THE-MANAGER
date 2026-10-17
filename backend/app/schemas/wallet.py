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


class RedemptionVerifyOut(BaseModel):
    amount: float
    used_at: datetime
