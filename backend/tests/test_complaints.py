"""Complaint rating tests — Reports feature (v1.5): the Resident who
raised a complaint can rate the Manager who resolved it, once, only
after it's actually RESOLVED/CLOSED, and it can never be changed
afterward (no update/delete endpoint exists)."""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, RelationshipType, Role, UserStatus
from app.models.identity import Property, PropertyResident, SocietyLocation, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_resident_manager_and_complaint(db_session: AsyncSession, society_id, admin_id):
    loc = SocietyLocation(society_id=society_id, name="Wing A", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()
    prop = Property(
        society_id=society_id, location_id=loc.id, house_number="101",
        house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
    )
    db_session.add(prop)
    await db_session.flush()

    resident = User(society_id=society_id, full_name="Resident", mobile="9500000001", status=UserStatus.ACTIVE)
    manager = User(society_id=society_id, full_name="Manager", mobile="9500000002", status=UserStatus.ACTIVE)
    db_session.add_all([resident, manager])
    await db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=now))
    db_session.add(UserRole(user_id=manager.id, role=Role.MANAGER, assigned_at=now))
    db_session.add(
        PropertyResident(
            society_id=society_id, property_id=prop.id, resident_id=resident.id,
            relationship_type=RelationshipType.OWNER, is_active=True, created_at=now,
        )
    )
    await db_session.commit()
    await db_session.refresh(resident)
    await db_session.refresh(manager)
    await db_session.refresh(prop)
    return resident, manager, prop


async def _create_and_assign_complaint(client, resident_headers, admin_headers, property_id, manager_id):
    resp = await client.post(
        "/api/v1/complaints",
        json={"property_id": str(property_id), "category": "Plumbing", "title": "Leaky tap", "description": "Kitchen tap is leaking"},
        headers=resident_headers,
    )
    assert resp.status_code == 200
    complaint_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/complaints/{complaint_id}/assign", json={"assigned_to": str(manager_id)}, headers=admin_headers
    )
    assert resp.status_code == 200
    return complaint_id


async def test_resident_can_rate_manager_after_complaint_resolved(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    resident, manager, prop = await _seed_resident_manager_and_complaint(db_session, society_id, admin_id)
    resident_headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    complaint_id = await _create_and_assign_complaint(client, resident_headers, admin_headers, prop.id, manager.id)

    resp = await client.patch(
        f"/api/v1/complaints/{complaint_id}/status", json={"status": "RESOLVED"}, headers=admin_headers
    )
    assert resp.status_code == 200

    resp = await client.post(f"/api/v1/complaints/{complaint_id}/rating", json={"rating": 5}, headers=resident_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["rating"] == 5
    assert body["manager_id"] == str(manager.id)
    assert body["complaint_id"] == complaint_id


async def test_rating_rejected_before_complaint_resolved(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    resident, manager, prop = await _seed_resident_manager_and_complaint(db_session, society_id, admin_id)
    resident_headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    complaint_id = await _create_and_assign_complaint(client, resident_headers, admin_headers, prop.id, manager.id)

    # Still IN_PROGRESS (assign_complaint sets it) — not resolved yet.
    resp = await client.post(f"/api/v1/complaints/{complaint_id}/rating", json={"rating": 4}, headers=resident_headers)
    assert resp.status_code == 400


async def test_rating_rejected_for_someone_elses_complaint(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    resident, manager, prop = await _seed_resident_manager_and_complaint(db_session, society_id, admin_id)
    resident_headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    complaint_id = await _create_and_assign_complaint(client, resident_headers, admin_headers, prop.id, manager.id)
    await client.patch(f"/api/v1/complaints/{complaint_id}/status", json={"status": "RESOLVED"}, headers=admin_headers)

    other_resident = User(society_id=society_id, full_name="Other Resident", mobile="9500000003", status=UserStatus.ACTIVE)
    db_session.add(other_resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=other_resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    await db_session.refresh(other_resident)
    other_headers = auth_headers(other_resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.post(f"/api/v1/complaints/{complaint_id}/rating", json={"rating": 1}, headers=other_headers)
    assert resp.status_code == 403


async def test_rating_cannot_be_given_twice(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    resident, manager, prop = await _seed_resident_manager_and_complaint(db_session, society_id, admin_id)
    resident_headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    complaint_id = await _create_and_assign_complaint(client, resident_headers, admin_headers, prop.id, manager.id)
    await client.patch(f"/api/v1/complaints/{complaint_id}/status", json={"status": "RESOLVED"}, headers=admin_headers)

    resp = await client.post(f"/api/v1/complaints/{complaint_id}/rating", json={"rating": 3}, headers=resident_headers)
    assert resp.status_code == 200

    resp = await client.post(f"/api/v1/complaints/{complaint_id}/rating", json={"rating": 5}, headers=resident_headers)
    assert resp.status_code == 409


async def test_rating_rejected_when_never_assigned_to_a_manager(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    resident, _manager, prop = await _seed_resident_manager_and_complaint(db_session, society_id, admin_id)
    resident_headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.post(
        "/api/v1/complaints",
        json={"property_id": str(prop.id), "category": "Other", "title": "Never assigned", "description": "..."},
        headers=resident_headers,
    )
    complaint_id = resp.json()["id"]
    # Admin resolves it directly without ever assigning a Manager.
    await client.patch(f"/api/v1/complaints/{complaint_id}/status", json={"status": "RESOLVED"}, headers=admin_headers)

    resp = await client.post(f"/api/v1/complaints/{complaint_id}/rating", json={"rating": 4}, headers=resident_headers)
    assert resp.status_code == 400


async def test_rating_out_of_range_rejected(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    resident, manager, prop = await _seed_resident_manager_and_complaint(db_session, society_id, admin_id)
    resident_headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    complaint_id = await _create_and_assign_complaint(client, resident_headers, admin_headers, prop.id, manager.id)
    await client.patch(f"/api/v1/complaints/{complaint_id}/status", json={"status": "RESOLVED"}, headers=admin_headers)

    resp = await client.post(f"/api/v1/complaints/{complaint_id}/rating", json={"rating": 6}, headers=resident_headers)
    assert resp.status_code == 422
    resp = await client.post(f"/api/v1/complaints/{complaint_id}/rating", json={"rating": 0}, headers=resident_headers)
    assert resp.status_code == 422
