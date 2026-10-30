"""admin_change_requests/approvals + one-Admin-per-society DB trigger

Revision ID: 0008_admin_change
Revises: 0007_owner_contact_details
Create Date: 2026-09-24

Two things:

1. A society could previously end up with more than one active Admin —
   nothing enforced "at most one". Adds a BEFORE INSERT/UPDATE trigger on
   user_roles (same pattern as 0002_role_society_trigger) that rejects an
   ADMIN role row if another active ADMIN already exists for that same
   society, checked via a join through users.society_id (no denormalized
   column needed, unlike sub_admin_scopes' own location_id).

2. admin_change_requests/admin_change_approvals — a Platform Owner-
   initiated replacement of a society's Admin, requiring unanimous
   Sub-admin sign-off (see app/models/identity.py's AdminChangeRequest/
   AdminChangeApproval docstrings for the full flow).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_admin_change"
down_revision: Union[str, None] = "0007_owner_contact_details"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, create_type=False)


_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION check_one_admin_per_society() RETURNS TRIGGER AS $$
DECLARE
    u_society_id UUID;
    other_admin_count INT;
BEGIN
    IF NEW.role = 'ADMIN' AND NEW.revoked_at IS NULL THEN
        SELECT society_id INTO u_society_id FROM users WHERE id = NEW.user_id;

        SELECT count(*) INTO other_admin_count
        FROM user_roles ur
        JOIN users u ON u.id = ur.user_id
        WHERE ur.role = 'ADMIN'
          AND ur.revoked_at IS NULL
          AND ur.id != NEW.id
          AND u.society_id = u_society_id;

        IF other_admin_count > 0 THEN
            RAISE EXCEPTION 'Society % already has an active Admin', u_society_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_TRIGGER_SQL = """
CREATE TRIGGER trg_check_one_admin_per_society
BEFORE INSERT OR UPDATE ON user_roles
FOR EACH ROW EXECUTE FUNCTION check_one_admin_per_society();
"""


def upgrade() -> None:
    op.execute(_FUNCTION_SQL)
    op.execute(_TRIGGER_SQL)

    op.create_table(
        "admin_change_requests",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("society_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("societies.id"), nullable=False),
        sa.Column("old_admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("new_admin_full_name", sa.String(length=150), nullable=False),
        sa.Column("new_admin_mobile", sa.String(length=15), nullable=False),
        sa.Column("new_admin_email", sa.String(length=200), nullable=True),
        sa.Column("status", _enum("role_request_status_enum"), nullable=False, server_default="PENDING"),
        sa.Column("initiated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("new_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["society_id", "old_admin_id"], ["users.society_id", "users.id"],
            name="fk_admin_change_requests_society_old_admin",
        ),
        sa.ForeignKeyConstraint(
            ["society_id", "new_admin_id"], ["users.society_id", "users.id"],
            name="fk_admin_change_requests_society_new_admin",
        ),
    )

    op.create_table(
        "admin_change_approvals",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("admin_change_requests.id"),
            nullable=False,
        ),
        sa.Column("sub_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "ux_admin_change_approvals_request_subadmin", "admin_change_approvals",
        ["request_id", "sub_admin_id"],
    )


def downgrade() -> None:
    op.drop_table("admin_change_approvals")
    op.drop_table("admin_change_requests")
    op.execute("DROP TRIGGER IF EXISTS trg_check_one_admin_per_society ON user_roles;")
    op.execute("DROP FUNCTION IF EXISTS check_one_admin_per_society();")
