"""complaint_ratings — Resident rates the Manager who resolved a complaint

Revision ID: 0013_complaint_ratings
Revises: 0012_manager_daily_tasks
Create Date: 2026-09-25

Part of the Reports feature: Admin/Sub-admin/Resident dashboards get a
Reports section covering monthly-maintenance totals, Manager task
completion, and complaint resolution — the last of which lets the
Resident who raised a complaint rate the Manager who resolved it, once
the complaint is RESOLVED/CLOSED. Ratings are immutable (no update/
delete path) and one per complaint (unique on complaint_id).
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_complaint_ratings"
down_revision: Union[str, None] = "0012_manager_daily_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "complaint_ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("society_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("societies.id"), nullable=False),
        sa.Column("complaint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("complaints.id"), nullable=False, unique=True),
        sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_complaint_ratings_rating_range"),
        sa.ForeignKeyConstraint(
            ["society_id", "resident_id"], ["users.society_id", "users.id"],
            name="fk_complaint_ratings_society_resident",
        ),
        sa.ForeignKeyConstraint(
            ["society_id", "manager_id"], ["users.society_id", "users.id"],
            name="fk_complaint_ratings_society_manager",
        ),
    )


def downgrade() -> None:
    op.drop_table("complaint_ratings")
