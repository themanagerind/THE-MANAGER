"""Self-service profile — GET/PATCH /users/me. One implementation shared by
every role (Admin, Resident, ...); mobile is never editable here (OTP login
identity, uniqueness-constrained)."""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, SocietyStatus, UserStatus
from app.models.identity import Society, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_admin(db_session: AsyncSession, mobile: str) -> tuple[User, Society]:
    society = Society(name="Profile Test Society", code=f"SOC-PROF-{uuid.uuid4().hex[:6]}", status=SocietyStatus.ACTIVE)
    db_session.add(society)
    await db_session.flush()
    admin = User(
        society_id=society.id, full_name="Original Name", mobile=mobile, email="original@example.com",
        status=UserStatus.ACTIVE,
    )
    db_session.add(admin)
    await db_session.flush()
    db_session.add(UserRole(user_id=admin.id, role=Role.ADMIN, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    await db_session.refresh(admin)
    return admin, society


async def test_get_my_profile_returns_full_details(client: AsyncClient, db_session: AsyncSession):
    admin, society = await _seed_admin(db_session, "9840000001")
    headers = auth_headers(admin.id, society.id, Role.ADMIN, [Role.ADMIN])

    resp = await client.get("/api/v1/users/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == "Original Name"
    assert body["mobile"] == "9840000001"
    assert body["email"] == "original@example.com"
    assert body["roles"] == ["ADMIN"]


async def test_get_my_profile_requires_auth(client: AsyncClient, db_session: AsyncSession):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


async def test_update_my_profile_changes_name_and_email(client: AsyncClient, db_session: AsyncSession):
    admin, society = await _seed_admin(db_session, "9840000002")
    headers = auth_headers(admin.id, society.id, Role.ADMIN, [Role.ADMIN])

    resp = await client.patch(
        "/api/v1/users/me", json={"full_name": "Updated Name", "email": "updated@example.com"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Name"
    assert resp.json()["email"] == "updated@example.com"
    assert resp.json()["mobile"] == "9840000002"  # unchanged — not editable here

    resp = await client.get("/api/v1/users/me", headers=headers)
    assert resp.json()["full_name"] == "Updated Name"
    assert resp.json()["email"] == "updated@example.com"


async def test_update_my_profile_can_clear_email(client: AsyncClient, db_session: AsyncSession):
    admin, society = await _seed_admin(db_session, "9840000003")
    headers = auth_headers(admin.id, society.id, Role.ADMIN, [Role.ADMIN])

    resp = await client.patch("/api/v1/users/me", json={"full_name": "Original Name"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] is None


async def test_update_my_profile_cannot_change_mobile(client: AsyncClient, db_session: AsyncSession):
    """mobile isn't part of ProfileUpdateIn at all — sending it is simply
    ignored (extra fields dropped), not a 422 or a silent mutation."""
    admin, society = await _seed_admin(db_session, "9840000004")
    headers = auth_headers(admin.id, society.id, Role.ADMIN, [Role.ADMIN])

    resp = await client.patch(
        "/api/v1/users/me", json={"full_name": "Original Name", "mobile": "9999999999"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["mobile"] == "9840000004"


async def test_update_my_profile_requires_auth(client: AsyncClient, db_session: AsyncSession):
    resp = await client.patch("/api/v1/users/me", json={"full_name": "Someone"})
    assert resp.status_code == 401


async def test_resident_can_view_and_update_own_profile(client: AsyncClient, db_session: AsyncSession):
    """Not Admin-specific — any authenticated role uses the same endpoint."""
    society = Society(name="Resident Profile Society", code=f"SOC-RESPROF-{uuid.uuid4().hex[:6]}", status=SocietyStatus.ACTIVE)
    db_session.add(society)
    await db_session.flush()
    resident = User(
        society_id=society.id, full_name="Resident Name", mobile="9840000005", status=UserStatus.ACTIVE,
    )
    db_session.add(resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()

    headers = auth_headers(resident.id, society.id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.patch(
        "/api/v1/users/me", json={"full_name": "Resident New Name"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Resident New Name"
    assert resp.json()["roles"] == ["RESIDENT"]
