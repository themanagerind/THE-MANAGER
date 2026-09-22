"""Manager To-Do endpoints — Section 16."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.manager_todo import (
    ManagerTodoCreateIn,
    ManagerTodoOut,
    ManagerTodoStatusUpdateIn,
    TaskSuggestionCreateIn,
    TaskSuggestionOut,
)
from app.schemas.pagination import Page, Pagination, pagination_params
from app.services import manager_todo_service

router = APIRouter(tags=["manager-todos"])


@router.post("/task-suggestions", response_model=TaskSuggestionOut)
async def add_task_suggestion(
    body: TaskSuggestionCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> TaskSuggestionOut:
    """Platform-global master catalog — visible to every society's Admin."""
    task = await manager_todo_service.add_task_suggestion(db, current.user_id, body.title)
    return TaskSuggestionOut.model_validate(task)


@router.get("/task-suggestions", response_model=list[TaskSuggestionOut])
async def list_task_suggestions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.MANAGER))],
) -> list[TaskSuggestionOut]:
    # Manager needs read access to resolve a to-do's task_suggestion_id to
    # its title in the UI — the catalog itself stays Admin-managed (add
    # above is still Admin-only), this is view-only.
    tasks = await manager_todo_service.list_task_suggestions(db)
    return [TaskSuggestionOut.model_validate(t) for t in tasks]


@router.post("/manager-todos", response_model=ManagerTodoOut)
async def assign_todo(
    body: ManagerTodoCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> ManagerTodoOut:
    todo = await manager_todo_service.assign_todo(
        db, current.society_id, body.manager_id, body.task_suggestion_id, body.task_date, current.user_id
    )
    return ManagerTodoOut.model_validate(todo)


@router.get("/manager-todos", response_model=Page[ManagerTodoOut])
async def list_todos(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.MANAGER))],
    pagination: Annotated[Pagination, Depends(pagination_params)],
) -> Page[ManagerTodoOut]:
    if current.active_role == Role.MANAGER:
        todos, total = await manager_todo_service.list_todos_for_manager(
            db, current.society_id, current.user_id, pagination.skip, pagination.limit
        )
    else:
        todos, total = await manager_todo_service.list_todos_for_society(
            db, current.society_id, pagination.skip, pagination.limit
        )
    return Page(items=[ManagerTodoOut.model_validate(t) for t in todos], total=total, skip=pagination.skip, limit=pagination.limit)


@router.patch("/manager-todos/{todo_id}/status", response_model=ManagerTodoOut)
async def update_status(
    todo_id: uuid.UUID,
    body: ManagerTodoStatusUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.MANAGER))],
) -> ManagerTodoOut:
    todo = await manager_todo_service.update_todo_status(
        db, current.society_id, todo_id, current.user_id, body.status
    )
    return ManagerTodoOut.model_validate(todo)
