"""Admin/Sub-admin visitor listing — GET /visitors was missing entirely
before this; only Resident's-own (/mine) and Guard's restricted
projection (/guard-view) existed."""
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, RelationshipType, Role, UserStatus
from app.models.identity import Property, PropertyResident, SocietyLocation, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_resident_with_visitor(db_session: AsyncSession, society_id):
    loc = SocietyLocation(society_id=society_id, name="Wing V", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()
    prop = Property(
        society_id=society_id, location_id=loc.id, house_number="V-1",
        house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
    )
    db_session.add(prop)
    await db_session.flush()

    resident = User(society_id=society_id, full_name="Visitor Test Resident", mobile="9300000001", status=UserStatus.ACTIVE)
    db_session.add(resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    db_session.add(
        PropertyResident(
            society_id=society_id, property_id=prop.id, resident_id=resident.id,
            relationship_type=RelationshipType.OWNER, is_active=True, created_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()
    await db_session.refresh(prop)
    await db_session.refresh(resident)
    return prop, resident


async def test_admin_can_list_all_visitors_in_society(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    fixtures = two_societies_with_admins
    society_id = fixtures["a"]["society_id"]
    admin_id = fixtures["a"]["admin_id"]
    prop, resident = await _seed_resident_with_visitor(db_session, society_id)

    resident_headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.post(
        "/api/v1/visitors",
        json={"property_id": str(prop.id), "visitor_name": "Courier Guy", "visit_date": date.today().isoformat()},
        headers=resident_headers,
    )
    assert resp.status_code == 200

    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    resp = await client.get("/api/v1/visitors", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["visitor_name"] == "Courier Guy"


async def test_admin_visitor_list_scoped_to_own_society(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    fixtures = two_societies_with_admins
    prop, resident = await _seed_resident_with_visitor(db_session, fixtures["a"]["society_id"])
    resident_headers = auth_headers(resident.id, fixtures["a"]["society_id"], Role.RESIDENT, [Role.RESIDENT])
    await client.post(
        "/api/v1/visitors",
        json={"property_id": str(prop.id), "visitor_name": "Courier Guy", "visit_date": date.today().isoformat()},
        headers=resident_headers,
    )

    other_admin_headers = auth_headers(fixtures["b"]["admin_id"], fixtures["b"]["society_id"], Role.ADMIN, [Role.ADMIN])
    resp = await client.get("/api/v1/visitors", headers=other_admin_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
