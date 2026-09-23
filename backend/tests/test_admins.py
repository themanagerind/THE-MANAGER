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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, SocietyStatus, UserStatus
from app.models.identity import Property, PropertyResident, Society, SocietyLocation, User, UserRole
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


async def _admin_signup_with_property(client: AsyncClient, society_id, mobile: str, house_number="A-101"):
    return await client.post(
        "/api/v1/admins/signup",
        json={
            "full_name": "Admin Who Also Lives Here",
            "mobile": mobile,
            "society_id": str(society_id),
            "property_location_name": "Wing A",
            "property_location_type": "WING",
            "house_number": house_number,
            "house_type": "FLAT",
            "floor_number": 2,
        },
    )


async def test_admin_signup_with_property_creates_unit_and_resident_role(
    client: AsyncClient, db_session: AsyncSession
):
    """Section 4 dual-role — describing your own unit at signup instead of
    a separate manual step after approval. Everything is created right
    away (location, property, PropertyResident, RESIDENT role) but stays
    inert until Platform Owner approval activates the account, exactly
    like the ADMIN role itself."""
    society = await _seed_active_society(db_session)
    resp = await _admin_signup_with_property(client, society.id, "9820000001")
    assert resp.status_code == 200
    admin_id = uuid.UUID(resp.json()["id"])

    location = (
        await db_session.execute(select(SocietyLocation).where(SocietyLocation.society_id == society.id))
    ).scalar_one()
    assert location.name == "Wing A"
    assert location.location_type.value == "WING"

    prop = (
        await db_session.execute(select(Property).where(Property.society_id == society.id))
    ).scalar_one()
    assert prop.house_number == "A-101"

    link = (
        await db_session.execute(select(PropertyResident).where(PropertyResident.resident_id == admin_id))
    ).scalar_one()
    assert link.property_id == prop.id
    assert link.relationship_type.value == "OWNER"
    assert link.is_active is True

    resident_role_count = (
        await db_session.execute(
            select(func.count()).select_from(UserRole).where(
                UserRole.user_id == admin_id, UserRole.role == Role.RESIDENT, UserRole.revoked_at.is_(None)
            )
        )
    ).scalar_one()
    assert resident_role_count == 1


async def test_admin_signup_with_property_stays_pending_until_approved(
    client: AsyncClient, db_session: AsyncSession
):
    """The RESIDENT role exists in the DB immediately, but the whole User
    row is still PENDING — get_current_user 401s on any non-ACTIVE user
    regardless of which roles they hold, so nothing is usable yet."""
    society = await _seed_active_society(db_session)
    resp = await _admin_signup_with_property(client, society.id, "9820000002")
    admin_id = resp.json()["id"]

    headers = auth_headers(uuid.UUID(admin_id), society.id, Role.RESIDENT, [Role.ADMIN, Role.RESIDENT])
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401


async def test_admin_signup_with_property_then_approval_enables_role_switch(
    client: AsyncClient, db_session: AsyncSession
):
    society = await _seed_active_society(db_session)
    resp = await _admin_signup_with_property(client, society.id, "9820000003")
    admin_id = resp.json()["id"]

    owner = await _seed_platform_owner(db_session, "9820000097")
    owner_headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])
    resp = await client.post(f"/api/v1/admins/{admin_id}/approval", json={"approve": True}, headers=owner_headers)
    assert resp.status_code == 200

    admin_headers = auth_headers(uuid.UUID(admin_id), society.id, Role.ADMIN, [Role.ADMIN])
    resp = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    assert set(resp.json()["available_roles"]) == {"ADMIN", "RESIDENT"}

    resp = await client.post(
        "/api/v1/auth/switch-role", json={"active_role": "RESIDENT"}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["active_role"] == "RESIDENT"


async def test_admin_signup_rejects_partial_property_fields(client: AsyncClient, db_session: AsyncSession):
    society = await _seed_active_society(db_session)
    resp = await client.post(
        "/api/v1/admins/signup",
        json={
            "full_name": "New Admin", "mobile": "9820000004", "society_id": str(society.id),
            "house_number": "A-101",  # rest of the property_* fields omitted
        },
    )
    assert resp.status_code == 422


async def test_admin_signup_flat_requires_floor_number(client: AsyncClient, db_session: AsyncSession):
    society = await _seed_active_society(db_session)
    resp = await client.post(
        "/api/v1/admins/signup",
        json={
            "full_name": "New Admin", "mobile": "9820000005", "society_id": str(society.id),
            "property_location_name": "Wing A", "property_location_type": "WING",
            "house_number": "A-101", "house_type": "FLAT",
        },
    )
    assert resp.status_code == 422


async def test_admin_signup_rejects_flat_under_a_row(client: AsyncClient, db_session: AsyncSession):
    society = await _seed_active_society(db_session)
    resp = await client.post(
        "/api/v1/admins/signup",
        json={
            "full_name": "New Admin", "mobile": "9820000006", "society_id": str(society.id),
            "property_location_name": "Row A", "property_location_type": "ROW",
            "house_number": "A-101", "house_type": "FLAT", "floor_number": 1,
        },
    )
    assert resp.status_code == 400


async def test_admin_signup_duplicate_house_number_rolls_back_whole_signup(
    client: AsyncClient, db_session: AsyncSession
):
    """A failure partway through the optional property capture must not
    leave a half-created Admin account behind — the same mobile number
    should be free to try the full signup again afterward."""
    society = await _seed_active_society(db_session)
    resp = await _admin_signup_with_property(client, society.id, "9820000007", house_number="A-101")
    assert resp.status_code == 200

    # Same house_number, different Admin -> the property insert collides.
    resp = await _admin_signup_with_property(client, society.id, "9820000008", house_number="A-101")
    assert resp.status_code == 409

    # The failed Admin's mobile number was never actually persisted —
    # proof the whole transaction rolled back, not just the property part.
    existing = (
        await db_session.execute(select(User).where(User.mobile == "9820000008"))
    ).scalar_one_or_none()
    assert existing is None

    # And it really can be retried clean, without a house_number clash.
    resp = await _admin_signup_with_property(client, society.id, "9820000008", house_number="A-102")
    assert resp.status_code == 200
