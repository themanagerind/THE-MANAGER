"""manager_daily_tasks + universal daily task-suggestions catalog

Revision ID: 0012_manager_daily_tasks
Revises: 0011_maintenance_due_penalty
Create Date: 2026-09-25

Admin previously had to call assign_todo (ManagerTodo) one date at a time
for a task that actually repeats every day (water tank check, garbage
follow-up, etc). manager_daily_tasks is the recurring template — Admin
ticks it on once per Manager (typically at staff-creation time) and
manager_todo_service generates that day's actual ManagerTodo row lazily
the next time the Manager reads their own list, same compute-on-read
approach as 0011's penalty accrual (no in-app scheduler exists).

Also seeds task_suggestions with a starter catalog of tasks that are
universal to day-to-day housing-society operations, so an Admin has a
ready checklist instead of typing every task from scratch. Add-only
(task_suggestions has no is_active/edit), so this is safe to run
alongside any tasks an Admin has already added themselves.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_manager_daily_tasks"
down_revision: Union[str, None] = "0011_maintenance_due_penalty"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DAILY_TASK_TITLES = [
    "Water tank cleaning & level check",
    "Common area & staircase cleaning check",
    "Garbage collection & disposal follow-up",
    "Parking area check",
    "Lift/elevator functioning check",
    "CCTV & security camera check",
    "Fire safety equipment check",
    "Generator/backup power check",
    "Garden & landscaping upkeep check",
    "Streetlight & common area lighting check",
    "Water supply & motor/pump check",
    "Security guard shift & attendance verification",
    "Visitor entry register review",
    "Notice board update check",
    "Pending complaints follow-up",
]


def upgrade() -> None:
    op.create_table(
        "manager_daily_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("society_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("societies.id"), nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_suggestion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("task_suggestions.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["society_id", "manager_id"], ["users.society_id", "users.id"],
            name="fk_manager_daily_tasks_society_manager",
        ),
        sa.UniqueConstraint("manager_id", "task_suggestion_id", name="ux_manager_daily_tasks_manager_task"),
    )

    # Idempotent on titles: a downgrade leaves these rows in place (see
    # downgrade() below), so a later re-upgrade must not re-insert them.
    conn = op.get_bind()
    existing = set(
        conn.execute(
            sa.text("SELECT title FROM task_suggestions WHERE created_by IS NULL AND title = ANY(:titles)"),
            {"titles": DAILY_TASK_TITLES},
        ).scalars()
    )
    to_insert = [title for title in DAILY_TASK_TITLES if title not in existing]
    if to_insert:
        task_suggestions = sa.table(
            "task_suggestions",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("title", sa.String),
            sa.column("created_by", postgresql.UUID(as_uuid=True)),
        )
        op.bulk_insert(
            task_suggestions,
            [{"id": uuid.uuid4(), "title": title, "created_by": None} for title in to_insert],
        )


def downgrade() -> None:
    op.drop_table("manager_daily_tasks")
    # task_suggestions rows are left in place: the table is add-only by
    # design (no edit/delete mechanism — see the model docstring), and a
    # ManagerTodo may already reference one of these by now, same as it
    # could for any Admin-typed suggestion.
