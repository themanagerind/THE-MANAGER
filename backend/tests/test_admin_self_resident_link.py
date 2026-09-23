"""Admin self-link — an Admin who also owns/rents a flat in their own
society can link themselves to it directly (POST /residents/self-link),
gaining a RESIDENT role on their EXISTING account instead of the public
signup form's "always creates a brand-new User row" behavior, which would
just collide with the (society_id, mobile) unique constraint. UserRole's
own docstring calls out ADMIN+RESIDENT as an intended dual-role
combination (Section 4)."""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, RelationshipType, Role, UserStatus
from app.models.identity import Property, PropertyResident, SocietyLocation, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_property(db_session: AsyncSession, society_id, house_number="A-101"):
    loc = (
        await db_session.execute(
            select(SocietyLocation).where(
                SocietyLocation.society_id == society_id, SocietyLocation.name == "Wing A"
            )
        )
    ).scalar_one_or_none()
    if loc is None:
        loc = SocietyLocation(society_id=society_id, name="Wing A", location_type=LocationType.WING)
        db_session.add(loc)
        await db_session.flush()
    prop = Property(
        society_id=society_id, location_id=loc.id, house_number=house_number,
        house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
    )
    db_session.add(prop)
    await db_session.commit()
    await db_session.refresh(prop)
    return prop


async def _resident_role_count(db_session: AsyncSession, user_id) -> int:
    return (
        await db_session.execute(
            select(func.count()).select_from(UserRole).where(
                UserRole.user_id == user_id, UserRole.role == Role.RESIDENT, UserRole.revoked_at.is_(None)
            )
        )
    ).scalar_one()


async def test_admin_can_link_self_as_resident_and_gains_resident_role(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    fixtures = two_societies_with_admins
    society_id = fixtures["a"]["society_id"]
    admin_id = fixtures["a"]["admin_id"]
    prop = await _seed_property(db_session, society_id)

    assert await _resident_role_count(db_session, admin_id) == 0

    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    resp = await client.post(
        "/api/v1/residents/self-link",
        json={"property_id": str(prop.id), "relationship_type": "OWNER"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["resident_id"] == str(admin_id)
    assert body["relationship_type"] == "OWNER"
    assert body["is_active"] is True

    assert await _resident_role_count(db_session, admin_id) == 1

    link = (
        await db_session.execute(select(PropertyResident).where(PropertyResident.resident_id == admin_id))
    ).scalar_one()
    assert link.property_id == prop.id


async def test_admin_self_link_does_not_duplicate_resident_role_on_second_property(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    fixtures = two_societies_with_admins
    society_id = fixtures["a"]["society_id"]
    admin_id = fixtures["a"]["admin_id"]
    prop1 = await _seed_property(db_session, society_id, "A-101")
    prop2 = await _seed_property(db_session, society_id, "A-102")
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp1 = await client.post(
        "/api/v1/residents/self-link",
        json={"property_id": str(prop1.id), "relationship_type": "OWNER"},
        headers=admin_headers,
    )
    assert resp1.status_code == 200

    resp2 = await client.post(
        "/api/v1/residents/self-link",
        json={"property_id": str(prop2.id), "relationship_type": "OWNER"},
        headers=admin_headers,
    )
    assert resp2.status_code == 200

    assert await _resident_role_count(db_session, admin_id) == 1


async def test_admin_self_link_lets_admin_switch_to_resident(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """After self-linking, /auth/me (re-derives available_roles fresh from
    the DB on every request — never trusts the JWT for this) must show
    RESIDENT as available, and switch-role to RESIDENT must succeed."""
    fixtures = two_societies_with_admins
    society_id = fixtures["a"]["society_id"]
    admin_id = fixtures["a"]["admin_id"]
    prop = await _seed_property(db_session, society_id)
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    await client.post(
        "/api/v1/residents/self-link",
        json={"property_id": str(prop.id), "relationship_type": "OWNER"},
        headers=admin_headers,
    )

    resp = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    assert set(resp.json()["available_roles"]) == {"ADMIN", "RESIDENT"}

    resp = await client.post(
        "/api/v1/auth/switch-role", json={"active_role": "RESIDENT"}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["active_role"] == "RESIDENT"


async def test_non_admin_cannot_self_link(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    prop = await _seed_property(db_session, society_id)

    resident = User(society_id=society_id, full_name="Some Resident", mobile="9300000099", status=UserStatus.ACTIVE)
    db_session.add(resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()

    resident_headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.post(
        "/api/v1/residents/self-link",
        json={"property_id": str(prop.id), "relationship_type": "OWNER"},
        headers=resident_headers,
    )
    assert resp.status_code == 403


async def test_admin_self_link_rejects_property_from_other_society(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    fixtures = two_societies_with_admins
    other_society_prop = await _seed_property(db_session, fixtures["b"]["society_id"])
    admin_headers = auth_headers(
        fixtures["a"]["admin_id"], fixtures["a"]["society_id"], Role.ADMIN, [Role.ADMIN]
    )

    resp = await client.post(
        "/api/v1/residents/self-link",
        json={"property_id": str(other_society_prop.id), "relationship_type": "OWNER"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


async def test_admin_self_link_as_tenant_requires_existing_active_owner(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    fixtures = two_societies_with_admins
    society_id = fixtures["a"]["society_id"]
    admin_id = fixtures["a"]["admin_id"]
    prop = await _seed_property(db_session, society_id)
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/residents/self-link",
        json={"property_id": str(prop.id), "relationship_type": "TENANT"},
        headers=admin_headers,
    )
    assert resp.status_code == 409
