"""owner_contact_name/mobile on property_residents

Revision ID: 0007_owner_contact_details
Revises: 0006_property_link_requests
Create Date: 2026-09-24

A Tenant can now sign up without the property's Owner having an account
in the system at all (see resident_service.signup_resident — the Section
12 "Tenant needs an active Owner" invariant no longer blocks self-service
signup/request paths). Without an Owner account, there's nowhere to look
up who the Owner actually is, so a Tenant can record the Owner's name/
mobile themselves, free-text, from their own Profile page — reference
info only, not a real account or login.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_owner_contact_details"
down_revision: Union[str, None] = "0006_property_link_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("property_residents", sa.Column("owner_contact_name", sa.String(length=150), nullable=True))
    op.add_column("property_residents", sa.Column("owner_contact_mobile", sa.String(length=15), nullable=True))


def downgrade() -> None:
    op.drop_column("property_residents", "owner_contact_mobile")
    op.drop_column("property_residents", "owner_contact_name")
