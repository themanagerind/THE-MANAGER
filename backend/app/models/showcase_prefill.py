"""
Showcase signup prefill — Resident -> Showcase (Ecom store) handoff
(user-requested, design reviewed and agreed with the Showcase team).

A Resident clicks "Shop Now"; THE-MANAGER issues an opaque, short-lived,
single-use token (no data inside it — see ShowcasePrefillToken docstring
for why). Showcase's backend redeems it server-to-server
(POST /showcase-prefill/redeem, same X-Store-Api-Key shared-secret pattern
as wallet redemption) to fetch the Resident's name/mobile/email/address/flat
and prefill its own signup form. Showcase itself gates revealing anything
beyond the mobile number until that same mobile is OTP-verified on its
side — that part is Showcase's own responsibility, not enforced here.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import CreatedAtOnlyMixin, UUIDPKMixin


class ShowcasePrefillToken(Base, UUIDPKMixin, CreatedAtOnlyMixin):
    """Deliberately opaque (random, no embedded claims) — a signed token
    carrying name/mobile/address would stop the data being *changed* but
    not being *read*, and this value travels through a URL (browser
    history, server/CDN logs, Referer headers, forwarded links). The real
    data is fetched by Showcase's backend via /redeem using this as a
    lookup key, never placed in anything the browser or a forwarded link
    can see directly."""

    __tablename__ = "showcase_prefill_tokens"

    resident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_used: Mapped[bool] = mapped_column(nullable=False, default=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Showcase's idempotency key for the /redeem call that consumed this
    # token — same reasoning and same normalize-empty-to-None handling as
    # wallet_service.verify_and_redeem_code's consumed_request_id (a
    # dropped response must be safely replayable without granting a
    # second redemption to a different caller).
    consumed_request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
