"""late-payment penalty on maintenance_dues + penalty_amount on payments

Revision ID: 0011_maintenance_due_penalty
Revises: 0010_user_avatar
Create Date: 2026-09-24

Admin sets an explicit due date per bill generation and can optionally
turn on a daily late-payment penalty (a fixed amount added per day once
the due date has passed, on top of the base maintenance amount) — opt-in
via penalty_enabled, never on by default. penalty_per_day is only set
when penalty_enabled is true. Admin can waive an already-enabled
penalty for a specific due at any time (penalty_waived) — the accrued
amount stops growing from that point (see maintenance_service.
compute_penalty, which treats a waived or disabled-penalty due as
always contributing 0). payments.penalty_amount records how much of a
given payment's total was penalty, folded in at submission time
(payment_service.submission) — same "compute on read, no cron" approach
as the rest of this schema (there's no in-app scheduler to accumulate a
running total against).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_maintenance_due_penalty"
down_revision: Union[str, None] = "0010_user_avatar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("maintenance_dues", sa.Column("penalty_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("maintenance_dues", sa.Column("penalty_per_day", sa.Numeric(12, 2), nullable=True))
    op.add_column("maintenance_dues", sa.Column("penalty_waived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("maintenance_dues", sa.Column("penalty_waived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("maintenance_dues", sa.Column("penalty_waived_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_maintenance_dues_penalty_waived_by", "maintenance_dues", "users", ["penalty_waived_by"], ["id"]
    )
    op.create_check_constraint(
        "ck_maintenance_dues_penalty_per_day_nonneg", "maintenance_dues", "penalty_per_day IS NULL OR penalty_per_day >= 0"
    )

    op.add_column("payments", sa.Column("penalty_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.create_check_constraint("ck_payments_penalty_amount_nonneg", "payments", "penalty_amount >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_payments_penalty_amount_nonneg", "payments", type_="check")
    op.drop_column("payments", "penalty_amount")

    op.drop_constraint("ck_maintenance_dues_penalty_per_day_nonneg", "maintenance_dues", type_="check")
    op.drop_constraint("fk_maintenance_dues_penalty_waived_by", "maintenance_dues", type_="foreignkey")
    op.drop_column("maintenance_dues", "penalty_waived_by")
    op.drop_column("maintenance_dues", "penalty_waived_at")
    op.drop_column("maintenance_dues", "penalty_waived")
    op.drop_column("maintenance_dues", "penalty_per_day")
    op.drop_column("maintenance_dues", "penalty_enabled")
