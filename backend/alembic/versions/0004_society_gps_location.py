"""societies.latitude/longitude

Revision ID: 0004_society_gps_location
Revises: 0003_floors_above_ground
Create Date: 2026-09-23

A society's GPS pin (Platform Owner copies lat/long from Google Maps
etc. at create or edit time) — the one field that stays optional
alongside the otherwise-required name/address/city/state/pincode. Always
both-or-neither and range-checked; see Society model's docstring comment.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_society_gps_location"
down_revision: Union[str, None] = "0003_floors_above_ground"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("societies", sa.Column("latitude", sa.Float, nullable=True))
    op.add_column("societies", sa.Column("longitude", sa.Float, nullable=True))
    op.create_check_constraint(
        "ck_societies_gps_both_or_neither",
        "societies",
        "(latitude IS NULL) = (longitude IS NULL)",
    )
    op.create_check_constraint(
        "ck_societies_latitude_range",
        "societies",
        "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
    )
    op.create_check_constraint(
        "ck_societies_longitude_range",
        "societies",
        "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_societies_longitude_range", "societies", type_="check")
    op.drop_constraint("ck_societies_latitude_range", "societies", type_="check")
    op.drop_constraint("ck_societies_gps_both_or_neither", "societies", type_="check")
    op.drop_column("societies", "longitude")
    op.drop_column("societies", "latitude")
