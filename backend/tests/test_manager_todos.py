"""Manager To-Do status transition tests — audit findings C7/C8.

Regression coverage for manager_todo_service.update_todo_status(): status
used to be overwritten unconditionally (any -> any), which allowed a task
to skip straight to DONE, or move backward out of DONE leaving a stale
completed_at behind. The fix enforces a one-step forward-only state
machine: PENDING -> IN_PROGRESS -> DONE, with DONE terminal.
"""
import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, TodoStatus, UserStatus
from app.models.identity import User, UserRole
from app.models.operations import ManagerTodo, TaskSuggestion
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_manager_and_tasks(db_session: AsyncSession, society_id) -> tuple[User, TaskSuggestion, TaskSuggestion]:
    mobile = f"93{uuid.uuid4().int % 10**8:08d}"
    manager = User(society_id=society_id, full_name="Manager", mobile=mobile, status=UserStatus.ACTIVE)
    db_session.add(manager)
    await db_session.flush()
    db_session.add(UserRole(user_id=manager.id, role=Role.MANAGER, assigned_at=datetime.now(timezone.utc)))

    task_a = TaskSuggestion(title="Water tank cleaning & level check", created_by=None)
    task_b = TaskSuggestion(title="Garbage collection & disposal follow-up", created_by=None)
    db_session.add_all([task_a, task_b])
    await db_session.commit()
    await db_session.refresh(manager)
    await db_session.refresh(task_a)
    await db_session.refresh(task_b)
    return manager, task_a, task_b


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


async def test_admin_sets_and_updates_managers_daily_task_checklist(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """A checkbox UI submits its whole current state each time — re-setting
    with a smaller set must turn the dropped task off (not delete it), and
    re-setting with it back in must reactivate the same row rather than
    duplicate it (unique on manager_id+task_suggestion_id)."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    manager, task_a, task_b = await _seed_manager_and_tasks(db_session, society_id)

    resp = await client.put(
        f"/api/v1/managers/{manager.id}/daily-tasks",
        json={"task_suggestion_ids": [str(task_a.id), str(task_b.id)]},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    titles = {row["task_title"] for row in resp.json()}
    assert titles == {task_a.title, task_b.title}
    assert all(row["is_active"] for row in resp.json())

    # Drop task_b.
    resp = await client.put(
        f"/api/v1/managers/{manager.id}/daily-tasks",
        json={"task_suggestion_ids": [str(task_a.id)]},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    by_title = {row["task_title"]: row["is_active"] for row in resp.json()}
    assert by_title == {task_a.title: True, task_b.title: False}

    resp = await client.get(f"/api/v1/managers/{manager.id}/daily-tasks", headers=admin_headers)
    assert resp.status_code == 200
    assert [row["task_title"] for row in resp.json()] == [task_a.title]

    # Bring task_b back — must reactivate the same row, not error/duplicate.
    resp = await client.put(
        f"/api/v1/managers/{manager.id}/daily-tasks",
        json={"task_suggestion_ids": [str(task_a.id), str(task_b.id)]},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert all(row["is_active"] for row in resp.json())


async def test_daily_task_checklist_rejects_non_manager_and_unknown_task(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    manager, task_a, _task_b = await _seed_manager_and_tasks(db_session, society_id)

    # admin_id itself doesn't hold a Manager role.
    resp = await client.put(
        f"/api/v1/managers/{admin_id}/daily-tasks",
        json={"task_suggestion_ids": [str(task_a.id)]},
        headers=admin_headers,
    )
    assert resp.status_code == 400

    resp = await client.put(
        f"/api/v1/managers/{manager.id}/daily-tasks",
        json={"task_suggestion_ids": [str(uuid.uuid4())]},
        headers=admin_headers,
    )
    assert resp.status_code == 404


async def test_manager_cannot_view_another_managers_daily_tasks(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    manager, _task_a, _task_b = await _seed_manager_and_tasks(db_session, society_id)
    other_manager, _a, _b = await _seed_manager_and_tasks(db_session, society_id)
    headers = auth_headers(manager.id, society_id, Role.MANAGER, [Role.MANAGER])

    resp = await client.get(f"/api/v1/managers/{other_manager.id}/daily-tasks", headers=headers)
    assert resp.status_code == 403

    resp = await client.get(f"/api/v1/managers/{manager.id}/daily-tasks", headers=headers)
    assert resp.status_code == 200


async def test_active_daily_tasks_auto_generate_todays_todo(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """The whole point of the checklist: once Admin has ticked a daily task
    on for a Manager, it should just show up in the Manager's to-do list
    every day without Admin re-assigning it — no manual assign_todo call
    needed. A second fetch on the same day must not create a duplicate."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    manager, task_a, task_b = await _seed_manager_and_tasks(db_session, society_id)
    manager_headers = auth_headers(manager.id, society_id, Role.MANAGER, [Role.MANAGER])

    resp = await client.put(
        f"/api/v1/managers/{manager.id}/daily-tasks",
        json={"task_suggestion_ids": [str(task_a.id), str(task_b.id)]},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    resp = await client.get("/api/v1/manager-todos", headers=manager_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert {i["task_suggestion_id"] for i in items} == {str(task_a.id), str(task_b.id)}
    assert all(i["status"] == "PENDING" for i in items)
    assert resp.json()["total"] == 2

    # Fetching again the same day must not duplicate.
    resp = await client.get("/api/v1/manager-todos", headers=manager_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 2

    # Turning a task off must not remove today's already-generated todo —
    # only stops future days from generating a new one.
    resp = await client.put(
        f"/api/v1/managers/{manager.id}/daily-tasks",
        json={"task_suggestion_ids": [str(task_a.id)]},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    resp = await client.get("/api/v1/manager-todos", headers=manager_headers)
    assert resp.json()["total"] == 2
