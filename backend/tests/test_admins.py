"""Admin self-signup (for an existing society) + Platform Owner approval.

Structurally mirrors test_residents.py's signup hardening tests (same
shape of problem: rate limit, society existence/ACTIVE check, clean
duplicate-signup error), plus the approval flow, which — unlike Resident
approval (scoped to the approving Admin's own society) — is scoped
globally to the Platform Owner across every society.
"""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, SocietyStatus, UserStatus
from app.models.identity import Society, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_active_society(db_session: AsyncSession) -> Society:
    society = Society(name="Admin Signup Test Society", code=f"SOC-ADMSIGNUP-{uuid.uuid4().hex[:6]}", status=SocietyStatus.ACTIVE)
    db_session.add(society)
    await db_session.commit()
    await db_session.refresh(society)
    return society


async def _seed_platform_owner(db_session: AsyncSession, mobile: str) -> User:
    owner = User(society_id=None, full_name="Platform Owner", mobile=mobile, status=UserStatus.ACTIVE)
    db_session.add(owner)
    await db_session.flush()
    db_session.add(UserRole(user_id=owner.id, role=Role.PLATFORM_OWNER, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    await db_session.refresh(owner)
    return owner


async def test_admin_signup_rejects_nonexistent_society(client: AsyncClient, db_session: AsyncSession):
    resp = await client.post(
        "/api/v1/admins/signup",
        json={"full_name": "New Admin", "mobile": "9810000001", "society_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


async def test_admin_signup_rejects_non_active_society(client: AsyncClient, db_session: AsyncSession):
    pending_society = Society(name="Pending Society", code=f"SOC-ADMPEND-{uuid.uuid4().hex[:6]}", status=SocietyStatus.PENDING)
    db_session.add(pending_society)
    await db_session.commit()
    await db_session.refresh(pending_society)

    resp = await client.post(
        "/api/v1/admins/signup",
        json={"full_name": "New Admin", "mobile": "9810000002", "society_id": str(pending_society.id)},
    )
    assert resp.status_code == 409


async def test_admin_signup_succeeds_for_active_society(client: AsyncClient, db_session: AsyncSession):
    society = await _seed_active_society(db_session)
    resp = await client.post(
        "/api/v1/admins/signup",
        json={"full_name": "New Admin", "mobile": "9810000003", "society_id": str(society.id)},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PENDING"


async def test_admin_duplicate_signup_returns_clean_conflict_not_500(client: AsyncClient, db_session: AsyncSession):
    society = await _seed_active_society(db_session)
    body = {"full_name": "New Admin", "mobile": "9810000004", "society_id": str(society.id)}

    resp1 = await client.post("/api/v1/admins/signup", json=body)
    assert resp1.status_code == 200

    resp2 = await client.post("/api/v1/admins/signup", json=body)
    assert resp2.status_code == 409


async def test_admin_signup_is_rate_limited_per_mobile(client: AsyncClient, db_session: AsyncSession):
    mobile = "9810000005"
    societies = [await _seed_active_society(db_session) for _ in range(7)]

    responses = []
    for society in societies:
        resp = await client.post(
            "/api/v1/admins/signup",
            json={"full_name": "New Admin", "mobile": mobile, "society_id": str(society.id)},
        )
        responses.append(resp.status_code)

    assert 429 in responses


async def test_platform_owner_can_approve_pending_admin_and_activate_login(
    client: AsyncClient, db_session: AsyncSession
):
    society = await _seed_active_society(db_session)
    resp = await client.post(
        "/api/v1/admins/signup",
        json={"full_name": "New Admin", "mobile": "9810000006", "society_id": str(society.id)},
    )
    admin_id = resp.json()["id"]

    owner = await _seed_platform_owner(db_session, "9810000099")
    owner_headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.get("/api/v1/admins/pending", headers=owner_headers)
    assert resp.status_code == 200
    assert any(a["id"] == admin_id for a in resp.json())

    resp = await client.post(f"/api/v1/admins/{admin_id}/approval", json={"approve": True}, headers=owner_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"

    # Approving twice is rejected, not silently re-applied.
    resp = await client.post(f"/api/v1/admins/{admin_id}/approval", json={"approve": True}, headers=owner_headers)
    assert resp.status_code == 409

    # Now active — an OTP-issued login token for this Admin actually works.
    admin_headers = auth_headers(uuid.UUID(admin_id), society.id, Role.ADMIN, [Role.ADMIN])
    resp = await client.get("/api/v1/properties", headers=admin_headers)
    assert resp.status_code == 200


async def test_platform_owner_can_reject_pending_admin(client: AsyncClient, db_session: AsyncSession):
    society = await _seed_active_society(db_session)
    resp = await client.post(
        "/api/v1/admins/signup",
        json={"full_name": "New Admin", "mobile": "9810000007", "society_id": str(society.id)},
    )
    admin_id = resp.json()["id"]

    owner = await _seed_platform_owner(db_session, "9810000098")
    owner_headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.post(f"/api/v1/admins/{admin_id}/approval", json={"approve": False}, headers=owner_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"


async def test_non_platform_owner_cannot_approve_admin_signup(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society = await _seed_active_society(db_session)
    resp = await client.post(
        "/api/v1/admins/signup",
        json={"full_name": "New Admin", "mobile": "9810000008", "society_id": str(society.id)},
    )
    admin_id = resp.json()["id"]

    other_admin_id = two_societies_with_admins["a"]["admin_id"]
    other_society_id = two_societies_with_admins["a"]["society_id"]
    headers = auth_headers(other_admin_id, other_society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(f"/api/v1/admins/{admin_id}/approval", json={"approve": True}, headers=headers)
    assert resp.status_code == 403
