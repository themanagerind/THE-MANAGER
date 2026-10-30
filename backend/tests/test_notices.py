"""Notices tests — Section 19.

notices.py (POST /notices, GET /notices) shipped with zero test coverage —
found while auditing the backend for gaps now that the frontend has
caught up (see CLAUDE.md Section 7). Covers who can create vs. list,
Security Guard's exclusion, per-society scoping, and pagination/order."""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, UserStatus
from app.models.identity import User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _add_user_with_role(db_session: AsyncSession, society_id, role: Role, mobile: str) -> User:
    user = User(society_id=society_id, full_name=f"{role.value} User", mobile=mobile, status=UserStatus.ACTIVE)
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserRole(user_id=user.id, role=role, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_admin_can_create_notice(client: AsyncClient, two_societies_with_admins):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/notices", json={"title": "Water Supply", "content": "Water will be shut off 10am-2pm."}, headers=admin_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Water Supply"
    assert body["content"] == "Water will be shut off 10am-2pm."
    assert body["society_id"] == str(society_id)
    assert body["created_by"] == str(admin_id)


@pytest.mark.parametrize("role", [Role.SUB_ADMIN, Role.MANAGER, Role.RESIDENT, Role.SECURITY_GUARD])
async def test_non_admin_roles_cannot_create_notice(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins, role):
    society_id = two_societies_with_admins["a"]["society_id"]
    user = await _add_user_with_role(db_session, society_id, role, "9600000001")
    headers = auth_headers(user.id, society_id, role, [role])

    resp = await client.post("/api/v1/notices", json={"title": "x", "content": "y"}, headers=headers)
    assert resp.status_code == 403


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SUB_ADMIN, Role.MANAGER, Role.RESIDENT])
async def test_roles_other_than_guard_can_list_notices(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins, role
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    resp = await client.post("/api/v1/notices", json={"title": "AGM", "content": "Annual meeting Sunday."}, headers=admin_headers)
    assert resp.status_code == 200

    if role == Role.ADMIN:
        headers = admin_headers
    else:
        user = await _add_user_with_role(db_session, society_id, role, "9600000002")
        headers = auth_headers(user.id, society_id, role, [role])

    resp = await client.get("/api/v1/notices", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "AGM"


async def test_security_guard_cannot_list_notices(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    society_id = two_societies_with_admins["a"]["society_id"]
    guard = await _add_user_with_role(db_session, society_id, Role.SECURITY_GUARD, "9600000003")
    headers = auth_headers(guard.id, society_id, Role.SECURITY_GUARD, [Role.SECURITY_GUARD])

    resp = await client.get("/api/v1/notices", headers=headers)
    assert resp.status_code == 403


async def test_notices_are_scoped_to_society(client: AsyncClient, two_societies_with_admins):
    society_a = two_societies_with_admins["a"]["society_id"]
    admin_a = two_societies_with_admins["a"]["admin_id"]
    society_b = two_societies_with_admins["b"]["society_id"]
    admin_b = two_societies_with_admins["b"]["admin_id"]

    resp = await client.post(
        "/api/v1/notices", json={"title": "Society A only", "content": "..."},
        headers=auth_headers(admin_a, society_a, Role.ADMIN, [Role.ADMIN]),
    )
    assert resp.status_code == 200

    resp = await client.get("/api/v1/notices", headers=auth_headers(admin_b, society_b, Role.ADMIN, [Role.ADMIN]))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_notice_list_is_paginated_newest_first(client: AsyncClient, two_societies_with_admins):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    for i in range(3):
        resp = await client.post("/api/v1/notices", json={"title": f"Notice {i}", "content": "..."}, headers=headers)
        assert resp.status_code == 200

    resp = await client.get("/api/v1/notices", params={"skip": 0, "limit": 2}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    # Newest first — the third notice created should lead.
    assert body["items"][0]["title"] == "Notice 2"
    assert body["items"][1]["title"] == "Notice 1"
