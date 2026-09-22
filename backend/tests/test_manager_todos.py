"""Manager To-Do status transition tests — audit findings C7/C8.

Regression coverage for manager_todo_service.update_todo_status(): status
used to be overwritten unconditionally (any -> any), which allowed a task
to skip straight to DONE, or move backward out of DONE leaving a stale
completed_at behind. The fix enforces a one-step forward-only state
machine: PENDING -> IN_PROGRESS -> DONE, with DONE terminal.
"""
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, TodoStatus, UserStatus
from app.models.identity import User, UserRole
from app.models.operations import ManagerTodo, TaskSuggestion
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_manager_with_todo(db_session: AsyncSession, society_id) -> tuple[User, ManagerTodo]:
    manager = User(society_id=society_id, full_name="Manager", mobile="9300000001", status=UserStatus.ACTIVE)
    db_session.add(manager)
    await db_session.flush()
    db_session.add(UserRole(user_id=manager.id, role=Role.MANAGER, assigned_at=datetime.now(timezone.utc)))

    task = TaskSuggestion(title="Check water tank", created_by=manager.id)
    db_session.add(task)
    await db_session.flush()

    todo = ManagerTodo(
        society_id=society_id, manager_id=manager.id, task_suggestion_id=task.id,
        task_date=date.today(), status=TodoStatus.PENDING, assigned_by=manager.id,
    )
    db_session.add(todo)
    await db_session.commit()
    await db_session.refresh(manager)
    await db_session.refresh(todo)
    return manager, todo


async def test_todo_status_progresses_one_step_at_a_time(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    manager, todo = await _seed_manager_with_todo(db_session, society_id)
    headers = auth_headers(manager.id, society_id, Role.MANAGER, [Role.MANAGER])

    resp = await client.patch(
        f"/api/v1/manager-todos/{todo.id}/status", json={"status": "IN_PROGRESS"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "IN_PROGRESS"

    resp = await client.patch(
        f"/api/v1/manager-todos/{todo.id}/status", json={"status": "DONE"}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "DONE"
    assert body["completed_at"] is not None


async def test_todo_status_cannot_skip_pending_to_done(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    manager, todo = await _seed_manager_with_todo(db_session, society_id)
    headers = auth_headers(manager.id, society_id, Role.MANAGER, [Role.MANAGER])

    resp = await client.patch(
        f"/api/v1/manager-todos/{todo.id}/status", json={"status": "DONE"}, headers=headers
    )
    assert resp.status_code == 400


async def test_todo_status_cannot_move_backward_out_of_done(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    manager, todo = await _seed_manager_with_todo(db_session, society_id)
    headers = auth_headers(manager.id, society_id, Role.MANAGER, [Role.MANAGER])

    await client.patch(f"/api/v1/manager-todos/{todo.id}/status", json={"status": "IN_PROGRESS"}, headers=headers)
    resp = await client.patch(f"/api/v1/manager-todos/{todo.id}/status", json={"status": "DONE"}, headers=headers)
    assert resp.status_code == 200

    await db_session.refresh(todo)
    completed_at_after_done = todo.completed_at
    assert completed_at_after_done is not None

    # DONE is terminal — neither reversal should be accepted, and
    # completed_at must stay exactly what it was set to (never go stale).
    resp = await client.patch(f"/api/v1/manager-todos/{todo.id}/status", json={"status": "IN_PROGRESS"}, headers=headers)
    assert resp.status_code == 400
    resp = await client.patch(f"/api/v1/manager-todos/{todo.id}/status", json={"status": "PENDING"}, headers=headers)
    assert resp.status_code == 400

    await db_session.refresh(todo)
    assert todo.status == TodoStatus.DONE
    assert todo.completed_at == completed_at_after_done


async def test_manager_can_read_task_suggestions_catalog(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Manager needs read access to the task-suggestions catalog to resolve
    a to-do's task_suggestion_id to a human title in the UI. Add (POST)
    stays Admin-only; this only grants GET."""
    society_id = two_societies_with_admins["a"]["society_id"]
    manager, _todo = await _seed_manager_with_todo(db_session, society_id)
    headers = auth_headers(manager.id, society_id, Role.MANAGER, [Role.MANAGER])

    resp = await client.get("/api/v1/task-suggestions", headers=headers)
    assert resp.status_code == 200
    assert any(t["title"] == "Check water tank" for t in resp.json())

    resp = await client.post("/api/v1/task-suggestions", json={"title": "New task"}, headers=headers)
    assert resp.status_code == 403
