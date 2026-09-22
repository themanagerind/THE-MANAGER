"""role/society DB invariant trigger

Revision ID: 0002_role_society_trigger
Revises: 0001_initial_schema
Create Date: 2026-09-13

Fix for audit round-8 item 7: the invariant "PLATFORM_OWNER -> users.society_id
IS NULL; every other role -> users.society_id IS NOT NULL" was previously
only enforced by service-layer code paths (app/models/identity.py's
UserRole comment flagged this explicitly as pending). This migration adds
a real BEFORE INSERT/UPDATE trigger on `user_roles` so the database itself
rejects a direct/accidental write that would violate it — not just the
application.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_role_society_trigger"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION check_role_society_invariant() RETURNS TRIGGER AS $$
DECLARE
    u_society_id UUID;
BEGIN
    SELECT society_id INTO u_society_id FROM users WHERE id = NEW.user_id;

    IF NEW.role = 'PLATFORM_OWNER' AND u_society_id IS NOT NULL THEN
        RAISE EXCEPTION 'PLATFORM_OWNER role requires users.society_id IS NULL (user_id=%)', NEW.user_id;
    END IF;

    IF NEW.role != 'PLATFORM_OWNER' AND u_society_id IS NULL THEN
        RAISE EXCEPTION 'Role % requires users.society_id IS NOT NULL (user_id=%)', NEW.role, NEW.user_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_TRIGGER_SQL = """
CREATE TRIGGER trg_check_role_society_invariant
BEFORE INSERT OR UPDATE ON user_roles
FOR EACH ROW EXECUTE FUNCTION check_role_society_invariant();
"""


def upgrade() -> None:
    op.execute(_FUNCTION_SQL)
    op.execute(_TRIGGER_SQL)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_check_role_society_invariant ON user_roles;")
    op.execute("DROP FUNCTION IF EXISTS check_role_society_invariant();")
