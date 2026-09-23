"""Resident-initiated property link requests — an already-ACTIVE Resident
requests (from their own Profile page) to link themselves to an
additional property; unlike the Admin-driven property-links endpoint
(immediate) this stays PENDING until the Admin approves it."""
import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, RelationshipType, Role, SocietyStatus, UserStatus
from app.models.identity import Property, PropertyResident, Society, SocietyLocation, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed(db_session: AsyncSession) -> dict:
    society = Society(name="Link Request Test Society", code=f"SOC-LINKREQ-{uuid.uuid4().hex[:6]}", status=SocietyStatus.ACTIVE)
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
    await db_session.flush()

    admin = User(society_id=society.id, full_name="Admin", mobile="9860000001", status=UserStatus.ACTIVE)
    resident = User(society_id=society.id, full_name="Resident", mobile="9860000002", status=UserStatus.ACTIVE)
    db_session.add_all([admin, resident])
    await db_session.flush()
    db_session.add_all([
        UserRole(user_id=admin.id, role=Role.ADMIN, assigned_at=datetime.now(timezone.utc)),
        UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)),
    ])
    await db_session.commit()

    return {"society": society, "wing": wing, "prop": prop, "admin": admin, "resident": resident}


def _resident_headers(seeded: dict) -> dict:
    return auth_headers(seeded["resident"].id, seeded["society"].id, Role.RESIDENT, [Role.RESIDENT])


def _admin_headers(seeded: dict) -> dict:
    return auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])


async def test_resident_can_submit_property_link_request(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    resp = await client.post(
        "/api/v1/residents/property-link-requests",
        json={"property_id": str(seeded["prop"].id), "relationship_type": "OWNER", "reason": "I bought this flat"},
        headers=_resident_headers(seeded),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["property_id"] == str(seeded["prop"].id)

    # Not yet a real link — approval is what creates it.
    link = (
        await db_session.execute(select(PropertyResident).where(PropertyResident.resident_id == seeded["resident"].id))
    ).scalar_one_or_none()
    assert link is None


async def test_request_requires_resident_role(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    resp = await client.post(
        "/api/v1/residents/property-link-requests",
        json={"property_id": str(seeded["prop"].id), "relationship_type": "OWNER"},
        headers=_admin_headers(seeded),
    )
    assert resp.status_code == 403


async def test_request_rejects_property_from_another_society(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    other = await _seed(db_session)
    resp = await client.post(
        "/api/v1/residents/property-link-requests",
        json={"property_id": str(other["prop"].id), "relationship_type": "OWNER"},
        headers=_resident_headers(seeded),
    )
    assert resp.status_code == 404


async def test_request_rejects_tenant_without_active_owner(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    resp = await client.post(
        "/api/v1/residents/property-link-requests",
        json={"property_id": str(seeded["prop"].id), "relationship_type": "TENANT"},
        headers=_resident_headers(seeded),
    )
    assert resp.status_code == 409


async def test_request_rejects_duplicate_pending(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    body = {"property_id": str(seeded["prop"].id), "relationship_type": "OWNER"}
    resp1 = await client.post("/api/v1/residents/property-link-requests", json=body, headers=_resident_headers(seeded))
    assert resp1.status_code == 200
    resp2 = await client.post("/api/v1/residents/property-link-requests", json=body, headers=_resident_headers(seeded))
    assert resp2.status_code == 409


async def test_request_rejects_if_already_actively_linked(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    db_session.add(
        PropertyResident(
            society_id=seeded["society"].id, property_id=seeded["prop"].id, resident_id=seeded["resident"].id,
            relationship_type=RelationshipType.OWNER, is_active=True, start_date=date.today(),
            created_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    resp = await client.post(
        "/api/v1/residents/property-link-requests",
        json={"property_id": str(seeded["prop"].id), "relationship_type": "OWNER"},
        headers=_resident_headers(seeded),
    )
    assert resp.status_code == 409


async def test_admin_can_list_pending_requests(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    await client.post(
        "/api/v1/residents/property-link-requests",
        json={"property_id": str(seeded["prop"].id), "relationship_type": "OWNER"},
        headers=_resident_headers(seeded),
    )
    resp = await client.get("/api/v1/residents/property-link-requests/pending", headers=_admin_headers(seeded))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["resident_id"] == str(seeded["resident"].id)


async def test_admin_list_pending_requires_admin(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    resp = await client.get("/api/v1/residents/property-link-requests/pending", headers=_resident_headers(seeded))
    assert resp.status_code == 403


async def test_resident_can_see_own_requests_of_any_status(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    resp = await client.post(
        "/api/v1/residents/property-link-requests",
        json={"property_id": str(seeded["prop"].id), "relationship_type": "OWNER"},
        headers=_resident_headers(seeded),
    )
    request_id = resp.json()["id"]
    await client.post(
        f"/api/v1/residents/property-link-requests/{request_id}/decision",
        json={"approve": False, "decision_reason": "Not verified"},
        headers=_admin_headers(seeded),
    )

    resp = await client.get("/api/v1/residents/property-link-requests/mine", headers=_resident_headers(seeded))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["status"] == "REJECTED"
    assert resp.json()[0]["decision_reason"] == "Not verified"


async def test_admin_approve_creates_the_real_link(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    resp = await client.post(
        "/api/v1/residents/property-link-requests",
        json={"property_id": str(seeded["prop"].id), "relationship_type": "OWNER"},
        headers=_resident_headers(seeded),
    )
    request_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/residents/property-link-requests/{request_id}/decision",
        json={"approve": True},
        headers=_admin_headers(seeded),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED"

    link = (
        await db_session.execute(select(PropertyResident).where(PropertyResident.resident_id == seeded["resident"].id))
    ).scalar_one()
    assert link.property_id == seeded["prop"].id
    assert link.relationship_type == RelationshipType.OWNER
    assert link.is_active is True


async def test_admin_reject_does_not_create_a_link(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    resp = await client.post(
        "/api/v1/residents/property-link-requests",
        json={"property_id": str(seeded["prop"].id), "relationship_type": "OWNER"},
        headers=_resident_headers(seeded),
    )
    request_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/residents/property-link-requests/{request_id}/decision",
        json={"approve": False, "decision_reason": "Couldn't verify ownership"},
        headers=_admin_headers(seeded),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"

    link = (
        await db_session.execute(select(PropertyResident).where(PropertyResident.resident_id == seeded["resident"].id))
    ).scalar_one_or_none()
    assert link is None


async def test_decide_twice_is_rejected(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    resp = await client.post(
        "/api/v1/residents/property-link-requests",
        json={"property_id": str(seeded["prop"].id), "relationship_type": "OWNER"},
        headers=_resident_headers(seeded),
    )
    request_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/residents/property-link-requests/{request_id}/decision",
        json={"approve": True},
        headers=_admin_headers(seeded),
    )
    assert resp.status_code == 200

    resp = await client.post(
        f"/api/v1/residents/property-link-requests/{request_id}/decision",
        json={"approve": True},
        headers=_admin_headers(seeded),
    )
    assert resp.status_code == 409


async def test_decide_requires_admin(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    resp = await client.post(
        "/api/v1/residents/property-link-requests",
        json={"property_id": str(seeded["prop"].id), "relationship_type": "OWNER"},
        headers=_resident_headers(seeded),
    )
    request_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/residents/property-link-requests/{request_id}/decision",
        json={"approve": True},
        headers=_resident_headers(seeded),
    )
    assert resp.status_code == 403


async def test_decide_rejects_request_from_another_society(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    other = await _seed(db_session)
    resp = await client.post(
        "/api/v1/residents/property-link-requests",
        json={"property_id": str(seeded["prop"].id), "relationship_type": "OWNER"},
        headers=_resident_headers(seeded),
    )
    request_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/residents/property-link-requests/{request_id}/decision",
        json={"approve": True},
        headers=_admin_headers(other),
    )
    assert resp.status_code == 404
