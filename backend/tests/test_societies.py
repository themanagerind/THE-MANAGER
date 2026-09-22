"""Society lifecycle tests — audit finding: PATCH /societies/{id}/status
accepted ANY SocietyStatus unconditionally, so a Platform Owner could send
PENDING at any time (ACTIVE -> PENDING, SUSPENDED -> PENDING) even though
PENDING is only supposed to be reachable via signup and only ever left via
POST /societies/{id}/approve."""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, SocietyStatus, UserStatus
from app.models.identity import Society, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_platform_owner(db_session: AsyncSession, mobile: str) -> User:
    owner = User(society_id=None, full_name="Platform Owner", mobile=mobile, status=UserStatus.ACTIVE)
    db_session.add(owner)
    await db_session.flush()
    db_session.add(UserRole(user_id=owner.id, role=Role.PLATFORM_OWNER, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    await db_session.refresh(owner)
    return owner


async def test_society_status_cannot_be_set_to_pending(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9700000001")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.patch(f"/api/v1/societies/{society_id}/status", json={"status": "PENDING"}, headers=headers)
    assert resp.status_code == 400

    society = (
        await db_session.execute(select(Society).where(Society.id == society_id))
    ).scalar_one()
    assert society.status == SocietyStatus.ACTIVE


async def test_pending_society_status_requires_approve_endpoint(
    client: AsyncClient, db_session: AsyncSession
):
    owner = await _seed_platform_owner(db_session, "9700000002")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    pending_society = Society(name="Pending Society", code="SOC-PENDING-1", status=SocietyStatus.PENDING)
    db_session.add(pending_society)
    await db_session.commit()
    await db_session.refresh(pending_society)

    # Trying to move it to SUSPENDED (or anything) via the generic status
    # endpoint before it's been approved must fail — /approve is the only
    # legitimate way out of PENDING.
    resp = await client.patch(
        f"/api/v1/societies/{pending_society.id}/status", json={"status": "SUSPENDED"}, headers=headers
    )
    assert resp.status_code == 409

    resp = await client.post(f"/api/v1/societies/{pending_society.id}/approve", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"


async def test_society_can_still_toggle_active_and_suspended(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9700000003")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.patch(f"/api/v1/societies/{society_id}/status", json={"status": "SUSPENDED"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUSPENDED"

    resp = await client.patch(f"/api/v1/societies/{society_id}/status", json={"status": "ACTIVE"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"
