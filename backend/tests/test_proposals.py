"""Proposal voting — GET /proposals/{id}'s my_vote field. Section 21/22.

A voter can change their vote until the proposal closes (cast_vote
upserts), so the detail response needs to tell the CALLER their own
current vote — otherwise the frontend has no way to show "you voted
APPROVE" and the Approve/Reject buttons look untouched after casting a
vote, which reads as "did that even register?" (the bug this fixes)."""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, UserStatus
from app.models.identity import User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_voters(db_session: AsyncSession, society_id, count: int = 1) -> list[User]:
    residents = []
    for i in range(count):
        r = User(society_id=society_id, full_name=f"Voter {i}", mobile=f"9320000{i:03d}", status=UserStatus.ACTIVE)
        db_session.add(r)
        await db_session.flush()
        db_session.add(UserRole(user_id=r.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
        residents.append(r)
    await db_session.commit()
    return residents


async def _create_proposal(client: AsyncClient, admin_headers: dict) -> str:
    resp = await client.post(
        "/api/v1/proposals",
        json={"scope_type": "SOCIETY", "title": "Repaint lobby", "description": "Repaint the main lobby"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    return resp.json()["id"]


async def test_my_vote_is_null_before_voting(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    subadmin = User(society_id=society_id, full_name="SubAdmin", mobile="9320009000", status=UserStatus.ACTIVE)
    db_session.add(subadmin)
    await db_session.flush()
    db_session.add(UserRole(user_id=subadmin.id, role=Role.SUB_ADMIN, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()

    residents = await _seed_voters(db_session, society_id, 1)
    proposal_id = await _create_proposal(client, admin_headers)

    resident_headers = auth_headers(residents[0].id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.get(f"/api/v1/proposals/{proposal_id}", headers=resident_headers)
    assert resp.status_code == 200
    assert resp.json()["my_vote"] is None


async def test_my_vote_reflects_cast_vote_and_updates_on_change(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    subadmin = User(society_id=society_id, full_name="SubAdmin", mobile="9320009001", status=UserStatus.ACTIVE)
    db_session.add(subadmin)
    await db_session.flush()
    db_session.add(UserRole(user_id=subadmin.id, role=Role.SUB_ADMIN, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()

    residents = await _seed_voters(db_session, society_id, 2)
    proposal_id = await _create_proposal(client, admin_headers)
    resident_headers = auth_headers(residents[0].id, society_id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.post(
        f"/api/v1/proposals/{proposal_id}/vote", json={"vote": "APPROVE"}, headers=resident_headers
    )
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/proposals/{proposal_id}", headers=resident_headers)
    assert resp.status_code == 200
    assert resp.json()["my_vote"] == "APPROVE"

    # Changing their mind before the proposal closes — cast_vote upserts.
    resp = await client.post(
        f"/api/v1/proposals/{proposal_id}/vote", json={"vote": "REJECT"}, headers=resident_headers
    )
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/proposals/{proposal_id}", headers=resident_headers)
    assert resp.status_code == 200
    assert resp.json()["my_vote"] == "REJECT"

    # Another resident who hasn't voted yet still sees null for themselves.
    other_headers = auth_headers(residents[1].id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.get(f"/api/v1/proposals/{proposal_id}", headers=other_headers)
    assert resp.status_code == 200
    assert resp.json()["my_vote"] is None
