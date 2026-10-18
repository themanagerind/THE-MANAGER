"""Showcase signup prefill endpoints — Resident "Shop Now" token issuance,
and redemption by Showcase's own backend (user-requested, design reviewed
with the Showcase team)."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role, require_store_api_key
from app.models.enums import Role
from app.schemas.showcase_prefill import PrefillCreateOut, PrefillRedeemIn, PrefillRedeemOut
from app.services import showcase_prefill_service

router = APIRouter(prefix="/showcase-prefill", tags=["showcase-prefill"])


@router.post("", response_model=PrefillCreateOut)
async def create_prefill_token(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> PrefillCreateOut:
    """Called when a Resident clicks "Shop Now" — the frontend is
    responsible for showing the DPDP consent line (name/mobile/address
    will be shared with Showcase) before calling this, and for building
    the redirect URL (<showcase-host>/welcome?prefill=<token> — path
    agreed with the Showcase team, see docs/integrations/the-manager-prefill.md)."""
    row = await showcase_prefill_service.generate_prefill_token(db, current.user_id)
    return PrefillCreateOut(token=row.token, expires_at=row.expires_at)


@router.post("/redeem", response_model=PrefillRedeemOut)
async def redeem_prefill_token(
    body: PrefillRedeemIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_store_api_key)],
) -> PrefillRedeemOut:
    """Called by Showcase's own backend — not a Resident, so authenticated
    via the shared X-Store-Api-Key header, never a Resident JWT. Redeems
    the token exactly once; a retry with the same body.request_id replays
    the same data, any other retry of an already-used/expired token is a
    clean 410 so Showcase can fall back to its normal signup form."""
    data = await showcase_prefill_service.redeem_prefill_token(db, body.token, body.request_id)
    return PrefillRedeemOut(**data)
