"""expense_bills.bill_image_key

Revision ID: 0016_expense_bill_image
Revises: 0015_account_headings
Create Date: 2026-09-25

Redesign (user-requested): Expense Bill approval no longer auto-posts to
Accounts on APPROVED (that call is removed from expense_bill_service.
decide_approval) — Admin now settles an APPROVED bill into Accounts
manually from the Accounts screen, picking a heading and entering an
amount capped at the bill's approved amount. As part of the same change,
every new expense bill must carry a photo of the physical bill/receipt
(reverses the old "No proof_url — never required" v1.1 decision).

bill_image_key is nullable at the DB level — same pattern as heading_id
in 0015 — so pre-existing bills aren't retroactively broken; "mandatory"
is enforced going forward at the Pydantic schema layer for new bills.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_expense_bill_image"
down_revision: Union[str, None] = "0015_account_headings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("expense_bills", sa.Column("bill_image_key", sa.String(300), nullable=True))


def downgrade() -> None:
    op.drop_column("expense_bills", "bill_image_key")
