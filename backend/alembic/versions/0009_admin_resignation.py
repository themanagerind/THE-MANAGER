"""admin_change_requests.new_admin_user_id — Admin self-resignation

Revision ID: 0009_admin_resignation
Revises: 0008_admin_change
Create Date: 2026-09-24

An Admin can now resign and pick their own replacement — an EXISTING
Resident or Sub-admin in their society, not a brand-new outside person
like the Platform Owner's "Change Admin" flow. Same
admin_change_requests/admin_change_approvals tables and unanimous-
Sub-admin-approval flow; new_admin_user_id (nullable) marks which path a
request took: set -> finalizing grants the ADMIN role to this existing
User; NULL (Platform Owner's flow, unchanged) -> finalizing creates a
brand-new User from new_admin_full_name/mobile/email.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_admin_resignation"
down_revision: Union[str, None] = "0008_admin_change"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_change_requests",
        sa.Column("new_admin_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_admin_change_requests_society_new_admin_user",
        "admin_change_requests", "users",
        ["society_id", "new_admin_user_id"], ["society_id", "id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_admin_change_requests_society_new_admin_user", "admin_change_requests", type_="foreignkey"
    )
    op.drop_column("admin_change_requests", "new_admin_user_id")
