"""property_link_requests — Resident-initiated property link, Admin-approved

Revision ID: 0006_property_link_requests
Revises: 0005_one_subadmin_per_location
Create Date: 2026-09-23

An already-ACTIVE Resident can now request to link themselves to an
(additional) property from their own Profile page, instead of only the
signup-time link or an Admin manually linking them. Unlike those two paths
(both immediate, no approval step), this one stays PENDING until the
Admin reviews it — approving is what actually creates the real
property_residents row (see app/services/resident_service.py's
decide_property_link_request). Reuses relationship_type_enum and
role_request_status_enum, both already created by 0001 — no new enum
types needed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_property_link_requests"
down_revision: Union[str, None] = "0005_one_subadmin_per_location"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, create_type=False)


def upgrade() -> None:
    op.create_table(
        "property_link_requests",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("society_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("societies.id"), nullable=False),
        sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", _enum("relationship_type_enum"), nullable=False),
        sa.Column("status", _enum("role_request_status_enum"), nullable=False, server_default="PENDING"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["society_id", "resident_id"], ["users.society_id", "users.id"],
            name="fk_property_link_requests_society_resident",
        ),
        sa.ForeignKeyConstraint(
            ["society_id", "property_id"], ["properties.society_id", "properties.id"],
            name="fk_property_link_requests_society_property",
        ),
    )
    op.create_index(
        "ux_property_link_requests_pending", "property_link_requests",
        ["resident_id", "property_id"],
        unique=True, postgresql_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_index("ux_property_link_requests_pending", table_name="property_link_requests")
    op.drop_table("property_link_requests")
