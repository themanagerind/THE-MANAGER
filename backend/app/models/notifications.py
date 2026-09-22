"""
Notifications Infra — Schema Spec v1.3, Section 2.6.

Table: push_subscriptions. This is the 32nd and final table — the model
layer (all groups) is now complete and matches the FINAL PROMPT Step 2
schema exactly.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import SubscriptionPlatform
from app.models.mixins import UUIDPKMixin
from app.models.pg_enum import pg_enum


class PushSubscription(Base, UUIDPKMixin):
    """Minimal delivery infra for Web Push / FCM (Section 1, audit gap #4).
    NOT a generic notification-feed table — no content, read-status, or
    audience-targeting logic here (that stays out of MVP scope)."""

    __tablename__ = "push_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # FCM token string, or serialized Web Push subscription (endpoint+keys) —
    # generic on purpose (v1.1 fix, not FCM-only)
    subscription_data: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[SubscriptionPlatform] = mapped_column(
        pg_enum(SubscriptionPlatform, "subscription_platform_enum"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # avoid duplicate active subscriptions per device
        Index(
            "ux_push_subscriptions_active",
            "user_id",
            "subscription_data",
            unique=True,
            postgresql_where="revoked_at IS NULL",
        ),
    )
