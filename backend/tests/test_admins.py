"""Admin self-signup (for an existing society) + Platform Owner approval.

Structurally mirrors test_residents.py's signup hardening tests (same
shape of problem: rate limit, society existence/ACTIVE check, clean
duplicate-signup error), plus the approval flow, which — unlike Resident
approval (scoped to the approving Admin's own society) — is scoped
globally to the Platform Owner across every society.

Every Admin signup is also a dual-role ADMIN+RESIDENT link (Section 4) —
existing_property_id/existing_property_relationship are mandatory; see
test_signup_property_link.py for the property-link-specific cases
(Tenant-needs-an-Owner, missing relationship, etc).
"""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, Role, SocietyStatus, UserStatus
from app.models.identity import Property, PropertyResident, Society, SocietyLocation, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_active_society_with_property(db_session: AsyncSession) -> tuple[Society, Property]:
    society = Society(name="Admin Signup Test Society", code=f"SOC-ADMSIGNUP-{uuid.uuid4().hex[:6]}", status=SocietyStatus.ACTIVE)
    db_session.add(society)
    await db_session.flush()
    wing = SocietyLocation(society_id=society.id, name="Wing A", location_type=LocationType.WING)
    db_session.add(wing)
    await db_session.flush()
    prop = Property(
        society_id=society.id, location_id=wing.id, house_number=f"A-{uuid.uuid4().hex[:4]}",
        house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
    )
    db_session.add(prop)
    await db_session.commit()
    await db_session.refresh(society)
    await db_session.refresh(prop)
    return society, prop


async def _seed_platform_owner(db_session: AsyncSession, mobile: str) -> User:
    owner = User(society_id=None, full_name="Platform Owner", mobile=mobile, status=UserStatus.ACTIVE)
    db_session.add(owner)
    await db_session.flush()
    db_session.add(UserRole(user_id=owner.id, role=Role.PLATFORM_OWNER, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    await db_session.refresh(owner)
    return owner


def _signup_body(society_id, mobile: str, property_id, relationship: str = "OWNER") -> dict:
    return {
        "full_name": "New Admin", "mobile": mobile, "society_id": str(society_id),
        "existing_property_id": str(property_id), "existing_property_relationship": relationship,
    }


async def test_admin_signup_rejects_nonexistent_society(client: AsyncClient, db_session: AsyncSession):
    resp = await client.post(
        "/api/v1/admins/signup",
        json=_signup_body(uuid.uuid4(), "9810000001", uuid.uuid4()),
    )
    assert resp.status_code == 404


async def test_admin_signup_rejects_non_active_society(client: AsyncClient, db_session: AsyncSession):
    pending_society = Society(name="Pending Society", code=f"SOC-ADMPEND-{uuid.uuid4().hex[:6]}", status=SocietyStatus.PENDING)
    db_session.add(pending_society)
    await db_session.commit()
    await db_session.refresh(pending_society)

    resp = await client.post(
        "/api/v1/admins/signup",
        json=_signup_body(pending_society.id, "9810000002", uuid.uuid4()),
    )
    assert resp.status_code == 409


async def test_admin_signup_requires_property(client: AsyncClient, db_session: AsyncSession):
    """existing_property_id/existing_property_relationship are mandatory —
    omitting either is a 422 before the request ever reaches the DB."""
    society, _ = await _seed_active_society_with_property(db_session)
    resp = await client.post(
        "/api/v1/admins/signup",
        json={"full_name": "New Admin", "mobile": "9810000003", "society_id": str(society.id)},
    )
    assert resp.status_code == 422


async def test_admin_signup_succeeds_for_active_society(client: AsyncClient, db_session: AsyncSession):
    society, prop = await _seed_active_society_with_property(db_session)
    resp = await client.post(
        "/api/v1/admins/signup",
        json=_signup_body(society.id, "9810000004", prop.id),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PENDING"


async def test_admin_duplicate_signup_returns_clean_conflict_not_500(client: AsyncClient, db_session: AsyncSession):
    society, prop = await _seed_active_society_with_property(db_session)
    body = _signup_body(society.id, "9810000005", prop.id)

    resp1 = await client.post("/api/v1/admins/signup", json=body)
    assert resp1.status_code == 200

    resp2 = await client.post("/api/v1/admins/signup", json=body)
    assert resp2.status_code == 409


async def test_admin_signup_is_rate_limited_per_mobile(client: AsyncClient, db_session: AsyncSession):
    mobile = "9810000006"
    seeded = [await _seed_active_society_with_property(db_session) for _ in range(7)]

    responses = []
    for society, prop in seeded:
        resp = await client.post(
            "/api/v1/admins/signup",
            json=_signup_body(society.id, mobile, prop.id),
        )
        responses.append(resp.status_code)

    assert 429 in responses


async def test_platform_owner_can_approve_pending_admin_and_activate_login(
    client: AsyncClient, db_session: AsyncSession
):
    society, prop = await _seed_active_society_with_property(db_session)
    resp = await client.post(
        "/api/v1/admins/signup",
        json=_signup_body(society.id, "9810000007", prop.id),
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
    society, prop = await _seed_active_society_with_property(db_session)
    resp = await client.post(
        "/api/v1/admins/signup",
        json=_signup_body(society.id, "9810000008", prop.id),
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
    society, prop = await _seed_active_society_with_property(db_session)
    resp = await client.post(
        "/api/v1/admins/signup",
        json=_signup_body(society.id, "9810000009", prop.id),
    )
    admin_id = resp.json()["id"]

    other_admin_id = two_societies_with_admins["a"]["admin_id"]
    other_society_id = two_societies_with_admins["a"]["society_id"]
    headers = auth_headers(other_admin_id, other_society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(f"/api/v1/admins/{admin_id}/approval", json={"approve": True}, headers=headers)
    assert resp.status_code == 403


async def test_admin_signup_creates_unit_link_and_resident_role(client: AsyncClient, db_session: AsyncSession):
    """Section 4 dual-role — every Admin signup also creates the
    PropertyResident link + RESIDENT role right away (mandatory, not
    optional), but stays inert until Platform Owner approval activates
    the account, exactly like the ADMIN role itself."""
    society, prop = await _seed_active_society_with_property(db_session)
    resp = await client.post(
        "/api/v1/admins/signup",
        json=_signup_body(society.id, "9820000001", prop.id),
    )
    assert resp.status_code == 200
    admin_id = uuid.UUID(resp.json()["id"])

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


async def test_admin_signup_stays_pending_until_approved(client: AsyncClient, db_session: AsyncSession):
    """The RESIDENT role exists in the DB immediately, but the whole User
    row is still PENDING — get_current_user 401s on any non-ACTIVE user
    regardless of which roles they hold, so nothing is usable yet."""
    society, prop = await _seed_active_society_with_property(db_session)
    resp = await client.post(
        "/api/v1/admins/signup",
        json=_signup_body(society.id, "9820000002", prop.id),
    )
    admin_id = resp.json()["id"]

    headers = auth_headers(uuid.UUID(admin_id), society.id, Role.RESIDENT, [Role.ADMIN, Role.RESIDENT])
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401


async def test_admin_signup_approval_enables_role_switch(client: AsyncClient, db_session: AsyncSession):
    society, prop = await _seed_active_society_with_property(db_session)
    resp = await client.post(
        "/api/v1/admins/signup",
        json=_signup_body(society.id, "9820000003", prop.id),
    )
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


async def test_admin_signup_rejects_property_from_another_society(client: AsyncClient, db_session: AsyncSession):
    society, _ = await _seed_active_society_with_property(db_session)
    _, other_prop = await _seed_active_society_with_property(db_session)

    resp = await client.post(
        "/api/v1/admins/signup",
        json=_signup_body(society.id, "9820000004", other_prop.id),
    )
    assert resp.status_code == 404
