"""Manager/Security Guard staff accounts — Admin creates them directly
(no property link, no approval wait, unlike Admin/Resident signup) since
they're third-party hired staff, not flat owners/tenants. There was
previously no way at all — API or UI — to assign either role to anyone
(the bug/gap this fixes)."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, UserStatus
from app.models.identity import User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def test_admin_creates_manager_active_immediately(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/staff",
        json={"full_name": "Vikram Manager", "mobile": "9700000001", "role": "MANAGER"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "MANAGER"
    assert body["status"] == "ACTIVE"
    assert body["full_name"] == "Vikram Manager"

    user = (
        await db_session.execute(select(User).where(User.mobile == "9700000001", User.society_id == society_id))
    ).scalar_one()
    assert user.status == UserStatus.ACTIVE
    role = (
        await db_session.execute(
            select(UserRole).where(UserRole.user_id == user.id, UserRole.role == Role.MANAGER)
        )
    ).scalar_one()
    assert role.revoked_at is None

    # No property link created — unlike Admin/Resident signup.
    from app.models.identity import PropertyResident
    links = (
        await db_session.execute(select(PropertyResident).where(PropertyResident.resident_id == user.id))
    ).scalars().all()
    assert links == []


async def test_admin_creates_security_guard(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/staff",
        json={"full_name": "Gate Guard", "mobile": "9700000002", "role": "SECURITY_GUARD"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "SECURITY_GUARD"

    # The newly created account can immediately log in and act as a Guard —
    # no approval wait.
    guard_id = resp.json()["id"]
    guard_headers = auth_headers(guard_id, society_id, Role.SECURITY_GUARD, [Role.SECURITY_GUARD])
    resp = await client.get("/api/v1/visitors/guard-view", headers=guard_headers)
    assert resp.status_code == 200


async def test_create_staff_rejects_resident_role(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Only MANAGER/SECURITY_GUARD go through this endpoint — Resident has
    its own signup+approval flow with a mandatory property link."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/staff",
        json={"full_name": "Sneaky Resident", "mobile": "9700000003", "role": "RESIDENT"},
        headers=admin_headers,
    )
    assert resp.status_code == 422


async def test_create_staff_duplicate_mobile_in_society_is_rejected(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/staff",
        json={"full_name": "First", "mobile": "9700000004", "role": "MANAGER"},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    resp = await client.post(
        "/api/v1/staff",
        json={"full_name": "Second", "mobile": "9700000004", "role": "SECURITY_GUARD"},
        headers=admin_headers,
    )
    assert resp.status_code == 409


async def test_create_staff_is_admin_only(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/staff",
        json={"full_name": "Some Manager", "mobile": "9700000005", "role": "MANAGER"},
        headers=admin_headers,
    )
    manager_id = resp.json()["id"]
    manager_headers = auth_headers(manager_id, society_id, Role.MANAGER, [Role.MANAGER])

    resp = await client.post(
        "/api/v1/staff",
        json={"full_name": "Another Manager", "mobile": "9700000006", "role": "MANAGER"},
        headers=manager_headers,
    )
    assert resp.status_code == 403


async def test_list_staff_returns_only_managers_and_guards_in_own_society(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_a = two_societies_with_admins["a"]["society_id"]
    admin_a = two_societies_with_admins["a"]["admin_id"]
    admin_a_headers = auth_headers(admin_a, society_a, Role.ADMIN, [Role.ADMIN])

    society_b = two_societies_with_admins["b"]["society_id"]
    admin_b = two_societies_with_admins["b"]["admin_id"]
    admin_b_headers = auth_headers(admin_b, society_b, Role.ADMIN, [Role.ADMIN])

    await client.post(
        "/api/v1/staff", json={"full_name": "A Manager", "mobile": "9700000007", "role": "MANAGER"},
        headers=admin_a_headers,
    )
    await client.post(
        "/api/v1/staff", json={"full_name": "A Guard", "mobile": "9700000008", "role": "SECURITY_GUARD"},
        headers=admin_a_headers,
    )
    await client.post(
        "/api/v1/staff", json={"full_name": "B Manager", "mobile": "9700000007", "role": "MANAGER"},
        headers=admin_b_headers,
    )

    resp = await client.get("/api/v1/staff", headers=admin_a_headers)
    assert resp.status_code == 200
    names = {r["full_name"] for r in resp.json()}
    assert names == {"A Manager", "A Guard"}


async def test_admin_removes_manager_and_they_lose_access(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/staff", json={"full_name": "Temp Manager", "mobile": "9700000009", "role": "MANAGER"},
        headers=admin_headers,
    )
    manager_id = resp.json()["id"]

    resp = await client.delete(f"/api/v1/staff/{manager_id}", headers=admin_headers)
    assert resp.status_code == 204

    resp = await client.get("/api/v1/staff", headers=admin_headers)
    assert manager_id not in {r["id"] for r in resp.json()}

    role = (
        await db_session.execute(
            select(UserRole).where(UserRole.user_id == manager_id, UserRole.role == Role.MANAGER)
        )
    ).scalar_one()
    assert role.revoked_at is not None


async def test_remove_staff_404_when_not_currently_staff(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.delete(f"/api/v1/staff/{admin_id}", headers=admin_headers)
    assert resp.status_code == 404
