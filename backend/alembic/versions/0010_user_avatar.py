"""avatar_key on users

Revision ID: 0010_user_avatar
Revises: 0009_admin_resignation
Create Date: 2026-09-24

Resident/Admin/Sub-admin can now upload a profile photo to show in the
sidebar in place of the default app logo — stores the local-disk storage
key (same pattern as PaymentProof.file_url), never a public URL. NULL
means "no custom photo, show the default logo".
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_user_avatar"
down_revision: Union[str, None] = "0009_admin_resignation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_key", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_key")
