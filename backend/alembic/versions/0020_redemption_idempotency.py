"""wallet_redemption_codes.consumed_request_id

Revision ID: 0020_redemption_idempotency
Revises: 0019_wallet_redemption_codes
Create Date: 2026-10-17

User-reported gap: if the store's /verify call succeeds on THE-MANAGER's
side (code marked used) but the response is lost to a network failure
before reaching the store, a naive retry got a 409 with no way to tell
"already used by someone else" apart from "already used by my own prior
call that I never saw the response to." Storing the store-supplied
idempotency key (request_id) alongside the used code lets a retry with
the SAME key safely replay the original 200.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_redemption_idempotency"
down_revision: Union[str, None] = "0019_wallet_redemption_codes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wallet_redemption_codes",
        sa.Column("consumed_request_id", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wallet_redemption_codes", "consumed_request_id")
