"""One active Sub-admin per Wing/Row

Revision ID: 0005_one_subadmin_per_location
Revises: 0004_society_gps_location
Create Date: 2026-09-23

Section 7: a Wing/Row should have at most one active Sub-admin at a time —
the existing ux_sub_admin_scopes_active index only stops the SAME person
being scoped to the SAME location twice, not two different residents both
holding active scope over the same location. Backstops the service-layer
check in subadmin_service.promote_to_subadmin/assign_additional_scope with
a real DB constraint, same "invariant enforced both in code and in the DB"
pattern as ux_properties_society_house etc.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005_one_subadmin_per_location"
down_revision: Union[str, None] = "0004_society_gps_location"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ux_sub_admin_scopes_location_active",
        "sub_admin_scopes",
        ["location_id"],
        unique=True,
        postgresql_where="revoked_at IS NULL",
    )


def downgrade() -> None:
    op.drop_index("ux_sub_admin_scopes_location_active", table_name="sub_admin_scopes")
