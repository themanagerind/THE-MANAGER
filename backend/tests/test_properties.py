"""Property lifecycle tests — audit finding: there was no way to mark a
property INACTIVE, and the shared resident authorization check didn't
look at property status at all."""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, RelationshipType, Role, UserStatus
from app.models.identity import Property, PropertyResident, SocietyLocation, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_resident_with_property(db_session: AsyncSession, society_id):
    loc = SocietyLocation(society_id=society_id, name="Wing A", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()
    prop = Property(
        society_id=society_id, location_id=loc.id, house_number="101",
        house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
    )
    db_session.add(prop)
    await db_session.flush()

    resident = User(society_id=society_id, full_name="Resident", mobile="9600000001", status=UserStatus.ACTIVE)
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


async def test_admin_can_toggle_property_active_status(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    prop, _resident = await _seed_resident_with_property(db_session, society_id)
    headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.patch(f"/api/v1/properties/{prop.id}/status", json={"status": "INACTIVE"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "INACTIVE"

    resp = await client.patch(f"/api/v1/properties/{prop.id}/status", json={"status": "ACTIVE"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"


async def test_inactive_property_blocks_resident_complaint(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """resident_owns_or_rents_property() (scope_service) gates complaints,
    visitors, amenities, and payments alike — this exercises it through the
    complaints endpoint as a representative case."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    prop, resident = await _seed_resident_with_property(db_session, society_id)

    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    resp = await client.patch(f"/api/v1/properties/{prop.id}/status", json={"status": "INACTIVE"}, headers=admin_headers)
    assert resp.status_code == 200

    resident_headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.post(
        "/api/v1/complaints",
        json={"property_id": str(prop.id), "category": "Plumbing", "title": "Leak", "description": "Leaking pipe"},
        headers=resident_headers,
    )
    assert resp.status_code == 403


async def test_property_status_update_scoped_to_society(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """An Admin can't flip a property's status in a DIFFERENT society."""
    fixtures = two_societies_with_admins
    prop, _resident = await _seed_resident_with_property(db_session, fixtures["a"]["society_id"])

    headers_b = auth_headers(fixtures["b"]["admin_id"], fixtures["b"]["society_id"], Role.ADMIN, [Role.ADMIN])
    resp = await client.patch(f"/api/v1/properties/{prop.id}/status", json={"status": "INACTIVE"}, headers=headers_b)
    assert resp.status_code == 404
