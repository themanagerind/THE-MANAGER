"""wallet_txn_type_enum: add REDEMPTION

Revision ID: 0018_wallet_redemption
Revises: 0017_resident_notifications
Create Date: 2026-10-17

"Activates" the existing resident Wallet for spending, not just earning
(user-requested) — a resident's own point-spend (e.g. a future Ecom PWA
discount redemption, not built yet) gets its own transaction type,
REDEMPTION, distinct from ADJUSTMENT (an Admin's correction). No change
to how points are earned — credit_maintenance_payment is untouched, still
credits the full payment amount regardless of on-time/late (explicitly
confirmed, not to be changed). wallet_service.redeem_points is the new,
ready-made debit primitive; no caller/endpoint exists yet since nothing
in the product spends points today.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0018_wallet_redemption"
down_revision: Union[str, None] = "0017_resident_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE wallet_txn_type_enum ADD VALUE IF NOT EXISTS 'REDEMPTION'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for enums — removing one requires
    # rebuilding the type (unused by any row, so not worth the churn for
    # a downgrade path nothing else in this codebase exercises either).
    pass
