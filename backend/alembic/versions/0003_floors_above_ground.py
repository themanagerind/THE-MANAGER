"""properties.floors_above_ground

Revision ID: 0003_floors_above_ground
Revises: 0002_role_society_trigger
Create Date: 2026-09-23

Platform Owner bulk structure generation (Section: Societies — Wings/Rows +
Properties): a BUNGALOW house's ground floor is always implied and doesn't
need recording; this column counts any additional storeys built above it,
set per-house after a bulk generate_bungalow_structure() call (which starts
every house at 0). Always 0 for FLAT — see the CHECK constraint below and
Property model's docstring comment.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_floors_above_ground"
down_revision: Union[str, None] = "0002_role_society_trigger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "properties",
        sa.Column("floors_above_ground", sa.Integer, nullable=False, server_default="0"),
    )
    op.alter_column("properties", "floors_above_ground", server_default=None)
    op.create_check_constraint(
        "ck_properties_floors_above_ground_bungalow_only",
        "properties",
        "house_type = 'BUNGALOW' OR floors_above_ground = 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_properties_floors_above_ground_bungalow_only", "properties", type_="check")
    op.drop_column("properties", "floors_above_ground")
