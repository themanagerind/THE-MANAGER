"""Showcase signup prefill service — Resident -> Showcase (Ecom store)
handoff (user-requested, design reviewed with the Showcase team).

Token is opaque (no embedded data — see ShowcasePrefillToken's docstring),
single-use, and expires 5 minutes after issue. A matching-request_id retry
of an already-redeemed token still replays the same data (Showcase's own
dropped-response problem, same reasoning as wallet_service's idempotency
fix) — but only a token that was never successfully redeemed can expire;
expiry never blocks a legitimate replay of one that was.
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RelationshipType
from app.models.identity import Property, PropertyResident, Society, User
from app.models.showcase_prefill import ShowcasePrefillToken

_TOKEN_VALIDITY = timedelta(minutes=5)


async def _unique_token(db: AsyncSession) -> str:
    """Pre-checks uniqueness with a SELECT rather than insert-and-catch —
    same reasoning as wallet_service._unique_redemption_code. 256 bits of
    randomness makes a real collision a formality, not a real retry loop."""
    for _ in range(5):
        token = secrets.token_urlsafe(32)
        existing = (
            await db.execute(select(ShowcasePrefillToken.id).where(ShowcasePrefillToken.token == token))
        ).scalar_one_or_none()
        if existing is None:
            return token
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Could not generate a unique prefill token")


async def generate_prefill_token(db: AsyncSession, resident_id: uuid.UUID) -> ShowcasePrefillToken:
    token = await _unique_token(db)
    row = ShowcasePrefillToken(
        resident_id=resident_id,
        token=token,
        expires_at=datetime.now(timezone.utc) + _TOKEN_VALIDITY,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _active_property_for(db: AsyncSession, resident_id: uuid.UUID) -> PropertyResident | None:
    """A Resident can own/rent multiple properties (Section 12) — picks
    deterministically rather than assuming exactly one: an active OWNER
    link first (an owner's own flat is the more natural "home address" for
    a delivery default than one they merely manage as a Tenant's
    landlord-on-file), falling back to the earliest-linked active one."""
    rows = (
        await db.execute(
            select(PropertyResident)
            .where(PropertyResident.resident_id == resident_id, PropertyResident.is_active.is_(True))
            .order_by(PropertyResident.created_at.asc())
        )
    ).scalars().all()
    if not rows:
        return None
    for row in rows:
        if row.relationship_type == RelationshipType.OWNER:
            return row
    return rows[0]


async def _profile_data(db: AsyncSession, resident_id: uuid.UUID) -> dict:
    user = (await db.execute(select(User).where(User.id == resident_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resident not found")

    address = None
    flat = None
    link = await _active_property_for(db, resident_id)
    if link is not None:
        prop = (await db.execute(select(Property).where(Property.id == link.property_id))).scalar_one_or_none()
        if prop is not None:
            society = (await db.execute(select(Society).where(Society.id == prop.society_id))).scalar_one_or_none()
            if society is not None:
                address = {
                    "society_name": society.name,
                    "line": society.address,
                    "city": society.city,
                    "state": society.state,
                    "pincode": society.pincode,
                }
            flat = {
                "number": prop.house_number,
                "floor": str(prop.floor_number) if prop.floor_number is not None else None,
            }

    return {
        "name": user.full_name,
        "mobile": user.mobile,
        "email": user.email,
        "address": address,
        "flat": flat,
    }


async def redeem_prefill_token(
    db: AsyncSession, token: str, request_id: str | None = None
) -> dict:
    if request_id is not None:
        request_id = request_id.strip() or None  # same empty-string normalization as wallet verify (audit finding)

    row = (
        await db.execute(
            select(ShowcasePrefillToken).where(ShowcasePrefillToken.token == token).with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prefill token not found")

    if row.is_used:
        if request_id and row.consumed_request_id == request_id:
            return await _profile_data(db, row.resident_id)
        raise HTTPException(status.HTTP_410_GONE, "Prefill token already used")

    if datetime.now(timezone.utc) > row.expires_at:
        raise HTTPException(status.HTTP_410_GONE, "Prefill token expired")

    row.is_used = True
    row.used_at = datetime.now(timezone.utc)
    row.consumed_request_id = request_id
    await db.commit()

    return await _profile_data(db, row.resident_id)
