"""Manager To-Do service — Section 16."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, TodoStatus
from app.models.operations import ManagerTodo, TaskSuggestion
from app.services.scope_service import user_has_active_role


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

    todo.status = new_status
    if new_status == TodoStatus.DONE:
        todo.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(todo)
    return todo
