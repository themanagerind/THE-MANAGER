"""Manager To-Do service — Section 16."""
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, TodoStatus
from app.models.operations import ManagerDailyTask, ManagerTodo, TaskSuggestion
from app.schemas.manager_todo import ManagerDailyTaskOut
from app.services.scope_service import user_has_active_role

# Audit findings C7/C8: status was previously overwritten unconditionally,
# allowing DONE -> PENDING/IN_PROGRESS or PENDING -> DONE, and leaving a
# stale completed_at behind after a reversal. DONE is terminal — a task
# that's finished can't move back, and the one-step progression below is
# the only path forward.
_ALLOWED_TRANSITIONS: dict[TodoStatus, set[TodoStatus]] = {
    TodoStatus.PENDING: {TodoStatus.IN_PROGRESS},
    TodoStatus.IN_PROGRESS: {TodoStatus.DONE},
    TodoStatus.DONE: set(),
}


async def add_task_suggestion(db: AsyncSession, created_by: uuid.UUID, title: str) -> TaskSuggestion:
    """Platform-global — any society's Admin adding a task makes it visible
    to every society's Admin (Section 16 RESOLVED). Add-only: no edit/deactivate."""
    task = TaskSuggestion(title=title, created_by=created_by)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def list_task_suggestions(db: AsyncSession) -> list[TaskSuggestion]:
    return (await db.execute(select(TaskSuggestion))).scalars().all()


async def assign_todo(
    db: AsyncSession,
    society_id: uuid.UUID,
    manager_id: uuid.UUID,
    task_suggestion_id: uuid.UUID,
    task_date,
    assigned_by: uuid.UUID,
) -> ManagerTodo:
    # HIGH fix (audit round-8): verify the target actually holds an active
    # Manager role in this society — composite FK only guarantees same-society.
    if not await user_has_active_role(db, manager_id, society_id, Role.MANAGER):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Target user does not hold an active Manager role in this society"
        )

    task = (
        await db.execute(select(TaskSuggestion).where(TaskSuggestion.id == task_suggestion_id))
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task suggestion not found in the master catalog")

    todo = ManagerTodo(
        society_id=society_id,
        manager_id=manager_id,
        task_suggestion_id=task_suggestion_id,
        task_date=task_date,
        status=TodoStatus.PENDING,
        assigned_by=assigned_by,
    )
    db.add(todo)
    await db.commit()
    await db.refresh(todo)
    return todo


async def set_daily_tasks(
    db: AsyncSession,
    society_id: uuid.UUID,
    manager_id: uuid.UUID,
    task_suggestion_ids: list[uuid.UUID],
    assigned_by: uuid.UUID,
) -> list[ManagerDailyTaskOut]:
    """Replaces this Manager's recurring daily-duty checklist with exactly
    the given set — matches a checkbox UI, which always submits its whole
    current state. Existing rows are toggled (is_active) rather than
    deleted, so completed-history ManagerTodo rows they already generated
    stay intact; only genuinely new task_suggestion_ids get a new row."""
    if not await user_has_active_role(db, manager_id, society_id, Role.MANAGER):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Target user does not hold an active Manager role in this society"
        )

    wanted = set(task_suggestion_ids)
    if wanted:
        found = (
            await db.execute(select(TaskSuggestion.id).where(TaskSuggestion.id.in_(wanted)))
        ).scalars().all()
        missing = wanted - set(found)
        if missing:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown task suggestion(s): {sorted(str(m) for m in missing)}")

    existing = (
        await db.execute(select(ManagerDailyTask).where(ManagerDailyTask.manager_id == manager_id))
    ).scalars().all()
    existing_by_task = {row.task_suggestion_id: row for row in existing}

    for task_id, row in existing_by_task.items():
        row.is_active = task_id in wanted

    for task_id in wanted - set(existing_by_task):
        db.add(
            ManagerDailyTask(
                society_id=society_id, manager_id=manager_id, task_suggestion_id=task_id,
                is_active=True, assigned_by=assigned_by,
            )
        )

    await db.commit()
    return await list_daily_tasks(db, society_id, manager_id, active_only=False)


async def list_daily_tasks(
    db: AsyncSession, society_id: uuid.UUID, manager_id: uuid.UUID, active_only: bool = True
) -> list[ManagerDailyTaskOut]:
    query = (
        select(ManagerDailyTask, TaskSuggestion.title)
        .join(TaskSuggestion, TaskSuggestion.id == ManagerDailyTask.task_suggestion_id)
        .where(ManagerDailyTask.society_id == society_id, ManagerDailyTask.manager_id == manager_id)
    )
    if active_only:
        query = query.where(ManagerDailyTask.is_active.is_(True))
    rows = (await db.execute(query)).all()
    return [
        ManagerDailyTaskOut(
            id=row.id, society_id=row.society_id, manager_id=row.manager_id,
            task_suggestion_id=row.task_suggestion_id, task_title=title,
            is_active=row.is_active, created_at=row.created_at,
        )
        for row, title in rows
    ]


async def _active_daily_task_rows(db: AsyncSession, society_id: uuid.UUID, manager_id: uuid.UUID) -> list[ManagerDailyTask]:
    return (
        await db.execute(
            select(ManagerDailyTask).where(
                ManagerDailyTask.society_id == society_id,
                ManagerDailyTask.manager_id == manager_id,
                ManagerDailyTask.is_active.is_(True),
            )
        )
    ).scalars().all()


async def _ensure_todays_todos_generated(db: AsyncSession, society_id: uuid.UUID, manager_id: uuid.UUID) -> None:
    """Turns each of this Manager's active daily-task templates into an
    actual today's ManagerTodo row, if one doesn't already exist — called
    right before a Manager reads their own list (no in-app scheduler
    exists, so generation happens lazily on read, same as compute_penalty
    elsewhere in this codebase)."""
    daily_tasks = await _active_daily_task_rows(db, society_id, manager_id)
    if not daily_tasks:
        return

    today = date.today()
    already_today = (
        await db.execute(
            select(ManagerTodo.task_suggestion_id).where(
                ManagerTodo.society_id == society_id,
                ManagerTodo.manager_id == manager_id,
                ManagerTodo.task_date == today,
            )
        )
    ).scalars().all()
    already_today = set(already_today)

    created = False
    for daily_task in daily_tasks:
        if daily_task.task_suggestion_id in already_today:
            continue
        db.add(
            ManagerTodo(
                society_id=society_id, manager_id=manager_id, task_suggestion_id=daily_task.task_suggestion_id,
                task_date=today, status=TodoStatus.PENDING, assigned_by=daily_task.assigned_by,
            )
        )
        created = True
    if created:
        await db.commit()


async def list_todos_for_society(db: AsyncSession, society_id: uuid.UUID, skip: int = 0, limit: int = 20) -> tuple[list[ManagerTodo], int]:
    from sqlalchemy import func
    total = (await db.execute(select(func.count()).select_from(ManagerTodo).where(ManagerTodo.society_id == society_id))).scalar_one()
    rows = (
        await db.execute(
            select(ManagerTodo).where(ManagerTodo.society_id == society_id)
            .order_by(ManagerTodo.task_date.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()
    return rows, total


async def list_todos_for_manager(db: AsyncSession, society_id: uuid.UUID, manager_id: uuid.UUID, skip: int = 0, limit: int = 20) -> tuple[list[ManagerTodo], int]:
    from sqlalchemy import func
    await _ensure_todays_todos_generated(db, society_id, manager_id)
    total = (
        await db.execute(
            select(func.count()).select_from(ManagerTodo)
            .where(ManagerTodo.society_id == society_id, ManagerTodo.manager_id == manager_id)
        )
    ).scalar_one()
    rows = (
        await db.execute(
            select(ManagerTodo).where(ManagerTodo.society_id == society_id, ManagerTodo.manager_id == manager_id)
            .order_by(ManagerTodo.task_date.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()
    return rows, total


async def update_todo_status(
    db: AsyncSession, society_id: uuid.UUID, todo_id: uuid.UUID, manager_id: uuid.UUID, new_status: TodoStatus
) -> ManagerTodo:
    todo = (
        await db.execute(
            select(ManagerTodo).where(ManagerTodo.id == todo_id, ManagerTodo.society_id == society_id)
        )
    ).scalar_one_or_none()
    if todo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "To-do not found in this society")
    if todo.manager_id != manager_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only update your own assigned tasks")

    if new_status not in _ALLOWED_TRANSITIONS[todo.status]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot move a task from {todo.status.value} to {new_status.value}",
        )

    todo.status = new_status
    if new_status == TodoStatus.DONE:
        todo.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(todo)
    return todo
