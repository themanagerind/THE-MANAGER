"""Profile photo self-service (POST/DELETE/GET /users/me/avatar) —
Resident/Admin/Sub-admin only, sidebar header (AppShell.tsx) — and
GET /societies/me, which powers the Security Guard sidebar header."""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, SocietyStatus, UserStatus
from app.models.identity import Society, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio

_FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100


async def _seed_user(db_session: AsyncSession, mobile: str, role: Role) -> tuple[User, Society]:
    society = Society(name="Avatar Test Society", code=f"SOC-AVT-{uuid.uuid4().hex[:6]}", status=SocietyStatus.ACTIVE)
    db_session.add(society)
    await db_session.flush()
    user = User(society_id=society.id, full_name="Some User", mobile=mobile, status=UserStatus.ACTIVE)
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserRole(user_id=user.id, role=role, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    await db_session.refresh(user)
    return user, society


async def test_resident_can_upload_and_fetch_own_avatar(client: AsyncClient, db_session: AsyncSession):
    resident, society = await _seed_user(db_session, "9850000001", Role.RESIDENT)
    headers = auth_headers(resident.id, society.id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.get("/api/v1/users/me", headers=headers)
    assert resp.json()["has_avatar"] is False

    resp = await client.post(
        "/api/v1/users/me/avatar", files={"file": ("me.jpg", _FAKE_JPEG, "image/jpeg")}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["has_avatar"] is True

    resp = await client.get("/api/v1/users/me", headers=headers)
    assert resp.json()["has_avatar"] is True

    resp = await client.get("/api/v1/users/me/avatar", headers=headers)
    assert resp.status_code == 200
    assert resp.content == _FAKE_JPEG


async def test_admin_and_subadmin_can_upload_avatar(client: AsyncClient, db_session: AsyncSession):
    admin, society = await _seed_user(db_session, "9850000002", Role.ADMIN)
    headers = auth_headers(admin.id, society.id, Role.ADMIN, [Role.ADMIN])
    resp = await client.post(
        "/api/v1/users/me/avatar", files={"file": ("me.jpg", _FAKE_JPEG, "image/jpeg")}, headers=headers
    )
    assert resp.status_code == 200

    sub_admin, society2 = await _seed_user(db_session, "9850000003", Role.SUB_ADMIN)
    headers2 = auth_headers(sub_admin.id, society2.id, Role.SUB_ADMIN, [Role.SUB_ADMIN])
    resp = await client.post(
        "/api/v1/users/me/avatar", files={"file": ("me.jpg", _FAKE_JPEG, "image/jpeg")}, headers=headers2
    )
    assert resp.status_code == 200


async def test_manager_and_guard_cannot_upload_avatar(client: AsyncClient, db_session: AsyncSession):
    manager, society = await _seed_user(db_session, "9850000004", Role.MANAGER)
    headers = auth_headers(manager.id, society.id, Role.MANAGER, [Role.MANAGER])
    resp = await client.post(
        "/api/v1/users/me/avatar", files={"file": ("me.jpg", _FAKE_JPEG, "image/jpeg")}, headers=headers
    )
    assert resp.status_code == 403

    guard, society2 = await _seed_user(db_session, "9850000005", Role.SECURITY_GUARD)
    headers2 = auth_headers(guard.id, society2.id, Role.SECURITY_GUARD, [Role.SECURITY_GUARD])
    resp = await client.post(
        "/api/v1/users/me/avatar", files={"file": ("me.jpg", _FAKE_JPEG, "image/jpeg")}, headers=headers2
    )
    assert resp.status_code == 403


async def test_avatar_rejects_non_image(client: AsyncClient, db_session: AsyncSession):
    resident, society = await _seed_user(db_session, "9850000006", Role.RESIDENT)
    headers = auth_headers(resident.id, society.id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.post(
        "/api/v1/users/me/avatar", files={"file": ("me.txt", b"not an image", "text/plain")}, headers=headers
    )
    assert resp.status_code == 400


async def test_get_avatar_404_when_none_set(client: AsyncClient, db_session: AsyncSession):
    resident, society = await _seed_user(db_session, "9850000007", Role.RESIDENT)
    headers = auth_headers(resident.id, society.id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.get("/api/v1/users/me/avatar", headers=headers)
    assert resp.status_code == 404


async def test_replacing_avatar_removes_old_one(client: AsyncClient, db_session: AsyncSession):
    resident, society = await _seed_user(db_session, "9850000008", Role.RESIDENT)
    headers = auth_headers(resident.id, society.id, Role.RESIDENT, [Role.RESIDENT])

    resp1 = await client.post(
        "/api/v1/users/me/avatar", files={"file": ("first.jpg", _FAKE_JPEG, "image/jpeg")}, headers=headers
    )
    assert resp1.status_code == 200

    second_jpeg = b"\xff\xd8\xff\xe0" + b"1" * 100
    resp2 = await client.post(
        "/api/v1/users/me/avatar", files={"file": ("second.jpg", second_jpeg, "image/jpeg")}, headers=headers
    )
    assert resp2.status_code == 200

    resp = await client.get("/api/v1/users/me/avatar", headers=headers)
    assert resp.content == second_jpeg


async def test_delete_avatar_reverts_to_default(client: AsyncClient, db_session: AsyncSession):
    resident, society = await _seed_user(db_session, "9850000009", Role.RESIDENT)
    headers = auth_headers(resident.id, society.id, Role.RESIDENT, [Role.RESIDENT])

    await client.post(
        "/api/v1/users/me/avatar", files={"file": ("me.jpg", _FAKE_JPEG, "image/jpeg")}, headers=headers
    )
    resp = await client.delete("/api/v1/users/me/avatar", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["has_avatar"] is False

    resp = await client.get("/api/v1/users/me/avatar", headers=headers)
    assert resp.status_code == 404


async def test_avatar_endpoints_require_auth(client: AsyncClient, db_session: AsyncSession):
    resp = await client.get("/api/v1/users/me/avatar")
    assert resp.status_code == 401


async def test_societies_me_returns_own_society_name(client: AsyncClient, db_session: AsyncSession):
    guard, society = await _seed_user(db_session, "9850000010", Role.SECURITY_GUARD)
    headers = auth_headers(guard.id, society.id, Role.SECURITY_GUARD, [Role.SECURITY_GUARD])
    resp = await client.get("/api/v1/societies/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"id": str(society.id), "name": "Avatar Test Society"}


async def test_societies_me_404_for_platform_owner(client: AsyncClient, db_session: AsyncSession):
    owner = User(society_id=None, full_name="Owner", mobile="9850000011", status=UserStatus.ACTIVE)
    db_session.add(owner)
    await db_session.flush()
    db_session.add(UserRole(user_id=owner.id, role=Role.PLATFORM_OWNER, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()

    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])
    resp = await client.get("/api/v1/societies/me", headers=headers)
    assert resp.status_code == 404


async def test_societies_me_requires_auth(client: AsyncClient, db_session: AsyncSession):
    resp = await client.get("/api/v1/societies/me")
    assert resp.status_code == 401
