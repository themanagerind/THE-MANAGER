"""wallet_redemption_codes

Revision ID: 0019_wallet_redemption_codes
Revises: 0018_wallet_redemption
Create Date: 2026-10-17

Resident -> Platform Owner Master Wallet point transfer (user-requested):
a Resident transfers points and gets a short, typeable code back — the
voucher they hand to a future, separately-built Ecom store, whose backend
calls POST /wallet-redemptions/verify (a static API-key, not a Resident
JWT) to redeem it exactly once. No Ecom-side schema here — this table
only tracks the code <-> amount <-> resident link on THE-MANAGER's side.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_wallet_redemption_codes"
down_revision: Union[str, None] = "0018_wallet_redemption"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wallet_redemption_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code", sa.String(8), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "wallet_transaction_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wallet_transactions.id"), nullable=False,
        ),
        sa.Column("is_used", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_wallet_redemption_codes_amount_positive"),
    )
    op.create_index("ix_wallet_redemption_codes_resident_id", "wallet_redemption_codes", ["resident_id"])


def downgrade() -> None:
    op.drop_index("ix_wallet_redemption_codes_resident_id", table_name="wallet_redemption_codes")
    op.drop_table("wallet_redemption_codes")
