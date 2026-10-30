"""complaint_ratings.resident_id -> rated_by

Revision ID: 0014_complaint_ratings_rated_by
Revises: 0013_complaint_ratings
Create Date: 2026-09-25

v1.6 extension: a Sub-admin can now rate any complaint within their
assigned Wing/Row scope (not just their own), or one they raised
themselves — not only a Resident rating their own complaint. The
column no longer always holds a Resident, so resident_id was a
misleading name; renamed to rated_by. Safe to rename outright — this
table has no rows yet from any real usage (0013 only just shipped).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0014_complaint_ratings_rated_by"
down_revision: Union[str, None] = "0013_complaint_ratings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("fk_complaint_ratings_society_resident", "complaint_ratings", type_="foreignkey")
    op.alter_column("complaint_ratings", "resident_id", new_column_name="rated_by")
    op.create_foreign_key(
        "fk_complaint_ratings_society_rated_by", "complaint_ratings", "users",
        ["society_id", "rated_by"], ["society_id", "id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_complaint_ratings_society_rated_by", "complaint_ratings", type_="foreignkey")
    op.alter_column("complaint_ratings", "rated_by", new_column_name="resident_id")
    op.create_foreign_key(
        "fk_complaint_ratings_society_resident", "complaint_ratings", "users",
        ["society_id", "resident_id"], ["society_id", "id"],
    )
