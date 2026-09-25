"""account_headings + heading_id on account_entries

Revision ID: 0015_account_headings
Revises: 0014_complaint_ratings_rated_by
Create Date: 2026-09-25

Admin previously free-typed a title for every manual Income/Expense
account entry, with no structure — no way to later group "how much did
we spend on Lift Maintenance this year" without eyeballing free text.
account_headings is a platform-global, add-only catalog (same shape as
manager_todo's task_suggestions) that Admin picks from instead; seeded
here with headings universal to Indian housing-society bookkeeping.
heading_id on account_entries is nullable — only ever set for MANUAL
entries going forward (service-level rule, see account_entry_service);
system-generated entries and any pre-existing MANUAL rows are
untouched.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_account_headings"
down_revision: Union[str, None] = "0014_complaint_ratings_rated_by"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INCOME_HEADINGS = [
    "Society Maintenance Charges",
    "Lawn/Garden Rent",
    "Scrap Sale",
    "Parking Charges",
    "Clubhouse/Hall Booking",
    "Interest on Fixed Deposit",
    "Late Payment Penalty/Interest",
    "Transfer Fee / NOC Charges",
    "Advertisement/Hoarding Income",
    "Non-Occupancy Charges",
    "Sinking Fund Contribution",
    "Festival/Donation Contribution",
]

EXPENSE_HEADINGS = [
    "Security Guard Expenses",
    "Sweeper/Housekeeping Expenses",
    "Lift Maintenance",
    "Ganesh Puja / Festival Expenses",
    "Water Bill",
    "Electricity Bill (Common Area)",
    "Garden/Landscaping Maintenance",
    "Repairs & Painting",
    "Pest Control",
    "Fire Safety Equipment Maintenance",
    "Insurance Premium",
    "Audit & Legal Fees",
    "Water Tank Cleaning",
    "CCTV/Security System Maintenance",
    "Office & Stationery Expenses",
]


def upgrade() -> None:
    op.create_table(
        "account_headings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("entry_type", postgresql.ENUM(name="entry_type_enum", create_type=False), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("entry_type", "title", name="ux_account_headings_type_title"),
    )
    op.add_column("account_entries", sa.Column("heading_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("account_headings.id"), nullable=True))

    account_headings = sa.table(
        "account_headings",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("entry_type", postgresql.ENUM(name="entry_type_enum", create_type=False)),
        sa.column("title", sa.String),
        sa.column("created_by", postgresql.UUID(as_uuid=True)),
    )
    rows = [{"id": uuid.uuid4(), "entry_type": "INCOME", "title": title, "created_by": None} for title in INCOME_HEADINGS]
    rows += [{"id": uuid.uuid4(), "entry_type": "EXPENSE", "title": title, "created_by": None} for title in EXPENSE_HEADINGS]
    op.bulk_insert(account_headings, rows)


def downgrade() -> None:
    op.drop_column("account_entries", "heading_id")
    op.drop_table("account_headings")
