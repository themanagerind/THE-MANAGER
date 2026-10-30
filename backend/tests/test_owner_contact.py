"""A Tenant self-recording the Owner's contact details on their own
Profile page (PATCH /residents/property-links/{id}/owner-contact) — added
alongside the relaxed "Tenant signup doesn't need an active Owner" rule,
since without an Owner account there's otherwise no record of who the
Owner is."""
import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, RelationshipType, Role, SocietyStatus, UserStatus
from app.models.identity import Property, PropertyResident, Society, SocietyLocation, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed(db_session: AsyncSession, relationship: RelationshipType = RelationshipType.TENANT) -> dict:
    society = Society(name="Owner Contact Test Society", code=f"SOC-OWNERCONTACT-{uuid.uuid4().hex[:6]}", status=SocietyStatus.ACTIVE)
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

    resident = User(society_id=society.id, full_name="Resident", mobile=f"9{uuid.uuid4().hex[:9]}", status=UserStatus.ACTIVE)
    other_resident = User(society_id=society.id, full_name="Other Resident", mobile=f"9{uuid.uuid4().hex[:9]}", status=UserStatus.ACTIVE)
    db_session.add_all([resident, other_resident])
    await db_session.flush()
    db_session.add_all([
        UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)),
        UserRole(user_id=other_resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)),
    ])

    link = PropertyResident(
        society_id=society.id, property_id=prop.id, resident_id=resident.id,
        relationship_type=relationship, is_active=True, start_date=date.today(),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(link)

    return {"society": society, "prop": prop, "resident": resident, "other_resident": other_resident, "link": link}


def _headers(user_id: uuid.UUID, society_id: uuid.UUID) -> dict:
    return auth_headers(user_id, society_id, Role.RESIDENT, [Role.RESIDENT])


async def test_tenant_can_set_owner_contact_details(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    resp = await client.patch(
        f"/api/v1/residents/property-links/{seeded['link'].id}/owner-contact",
        json={"owner_contact_name": "Ramesh Owner", "owner_contact_mobile": "9812345678"},
        headers=_headers(seeded["resident"].id, seeded["society"].id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["owner_contact_name"] == "Ramesh Owner"
    assert body["owner_contact_mobile"] == "9812345678"


async def test_tenant_can_clear_owner_contact_details(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    await client.patch(
        f"/api/v1/residents/property-links/{seeded['link'].id}/owner-contact",
        json={"owner_contact_name": "Ramesh Owner", "owner_contact_mobile": "9812345678"},
        headers=_headers(seeded["resident"].id, seeded["society"].id),
    )
    resp = await client.patch(
        f"/api/v1/residents/property-links/{seeded['link'].id}/owner-contact",
        json={"owner_contact_name": None, "owner_contact_mobile": None},
        headers=_headers(seeded["resident"].id, seeded["society"].id),
    )
    assert resp.status_code == 200
    assert resp.json()["owner_contact_name"] is None
    assert resp.json()["owner_contact_mobile"] is None


async def test_owner_link_rejects_owner_contact_details(client: AsyncClient, db_session: AsyncSession):
    """An Owner's own link doesn't need this — they ARE the Owner."""
    seeded = await _seed(db_session, relationship=RelationshipType.OWNER)
    resp = await client.patch(
        f"/api/v1/residents/property-links/{seeded['link'].id}/owner-contact",
        json={"owner_contact_name": "Someone Else"},
        headers=_headers(seeded["resident"].id, seeded["society"].id),
    )
    assert resp.status_code == 400


async def test_cannot_set_owner_contact_on_someone_elses_link(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    resp = await client.patch(
        f"/api/v1/residents/property-links/{seeded['link'].id}/owner-contact",
        json={"owner_contact_name": "Sneaky"},
        headers=_headers(seeded["other_resident"].id, seeded["society"].id),
    )
    assert resp.status_code == 404
