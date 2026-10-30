"""Showcase signup prefill schemas — Resident -> Showcase handoff
(user-requested; design reviewed with the Showcase team)."""
from datetime import datetime

from pydantic import BaseModel, Field


class PrefillCreateOut(BaseModel):
    token: str
    expires_at: datetime


class PrefillRedeemIn(BaseModel):
    token: str
    # Showcase's idempotency key for this specific redeem attempt — see
    # wallet-redemption verify's request_id for the exact same reasoning.
    request_id: str | None = Field(default=None, max_length=100)


class PrefillAddressOut(BaseModel):
    society_name: str
    line: str | None
    city: str | None
    state: str | None
    pincode: str | None


class PrefillFlatOut(BaseModel):
    number: str
    floor: str | None


class PrefillRedeemOut(BaseModel):
    name: str
    mobile: str
    email: str | None
    # None only if the Resident has no active property link at all — an
    # edge case (e.g. link pending Admin approval), not expected to be
    # common; Showcase's own form just leaves address/flat blank then.
    address: PrefillAddressOut | None
    flat: PrefillFlatOut | None
