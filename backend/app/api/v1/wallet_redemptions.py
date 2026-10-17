"""Wallet redemption endpoints — Resident -> Platform Owner Master Wallet
point transfer, and code verification for a future, separately-built
Ecom store (user-requested)."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role, require_store_api_key
from app.models.enums import Role
from app.schemas.pagination import Page, Pagination, pagination_params
from app.schemas.wallet import (
    RedemptionCodeOut,
    RedemptionCreateIn,
    RedemptionVerifyIn,
    RedemptionVerifyOut,
)
from app.services import wallet_service

router = APIRouter(prefix="/wallet-redemptions", tags=["wallet-redemptions"])


@router.post("", response_model=RedemptionCodeOut)
async def create_redemption(
    body: RedemptionCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> RedemptionCodeOut:
    """Debits the Resident's own wallet, credits the Platform Owner's
    Master Wallet, and returns a short code to redeem at a (future) Ecom
    store — see wallet_service.transfer_to_master_wallet."""
    redemption = await wallet_service.transfer_to_master_wallet(db, current.user_id, body.amount)
    return RedemptionCodeOut.model_validate(redemption)


@router.get("/mine", response_model=Page[RedemptionCodeOut])
async def list_my_redemptions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
    pagination: Annotated[Pagination, Depends(pagination_params)],
) -> Page[RedemptionCodeOut]:
    rows, total = await wallet_service.list_redemption_codes(
        db, current.user_id, pagination.skip, pagination.limit
    )
    return Page(
        items=[RedemptionCodeOut.model_validate(r) for r in rows],
        total=total, skip=pagination.skip, limit=pagination.limit,
    )


@router.post("/verify", response_model=RedemptionVerifyOut)
async def verify_redemption(
    body: RedemptionVerifyIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_store_api_key)],
) -> RedemptionVerifyOut:
    """Called by a (future, separately-built) Ecom store's own backend —
    not a Resident, so authenticated via a shared X-Store-Api-Key header
    (require_store_api_key), never a Resident JWT. Marks the code used
    exactly once; a retry with the same body.request_id replays that same
    success, any other retry of an already-used code is a clean 409."""
    redemption = await wallet_service.verify_and_redeem_code(db, body.code, body.request_id)
    amount_paise = round(float(redemption.amount) * 100)
    return RedemptionVerifyOut(amount_paise=amount_paise, used_at=redemption.used_at)
