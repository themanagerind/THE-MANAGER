"""showcase_prefill_tokens

Revision ID: 0021_showcase_prefill
Revises: 0020_redemption_idempotency
Create Date: 2026-10-18

Resident -> Showcase (Ecom store) signup prefill (user-requested, design
reviewed with the Showcase team): an opaque, short-lived, single-use token
a Resident gets on "Shop Now", redeemed server-to-server by Showcase's own
backend via POST /showcase-prefill/redeem (X-Store-Api-Key, same pattern
as wallet redemption) to fetch name/mobile/email/address/flat. No Showcase-
side schema here — this table only tracks the token <-> resident link and
its one-time-use state on THE-MANAGER's side.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_showcase_prefill"
down_revision: Union[str, None] = "0020_redemption_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "showcase_prefill_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_used", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_request_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_showcase_prefill_tokens_resident_id", "showcase_prefill_tokens", ["resident_id"])


def downgrade() -> None:
    op.drop_index("ix_showcase_prefill_tokens_resident_id", table_name="showcase_prefill_tokens")
    op.drop_table("showcase_prefill_tokens")
