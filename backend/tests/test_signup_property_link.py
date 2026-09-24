"""Self-service property linking at signup (Admin AND Resident) — property
link now happens at signup time, done by the person signing up, instead of
an Admin manually linking it afterward from the "Link property" modal.
Covers: the public property-picker endpoint, Resident signup's required
property_id/relationship_type, and Admin signup's equally mandatory
existing_property_id/existing_property_relationship (Section 4 — every
Admin is ADMIN+RESIDENT; see test_admins.py for the rest of the Admin
signup/approval coverage)."""
import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, RelationshipType, Role, SocietyStatus, UserStatus
from app.models.identity import Property, PropertyResident, Society, SocietyLocation, User, UserRole

pytestmark = pytest.mark.asyncio


async def _seed_society(db_session: AsyncSession, active: bool = True) -> Society:
    society = Society(
        name="Property Link Test Society", code=f"SOC-PLINK-{uuid.uuid4().hex[:6]}",
        status=SocietyStatus.ACTIVE if active else SocietyStatus.PENDING,
    )
    db_session.add(society)
    await db_session.commit()
    await db_session.refresh(society)
    return society


async def _seed_property(
    db_session: AsyncSession, society: Society, house_number: str | None = None, status: str = "ACTIVE"
) -> Property:
    wing = SocietyLocation(society_id=society.id, name=f"Wing {uuid.uuid4().hex[:6]}", location_type=LocationType.WING)
    db_session.add(wing)
    await db_session.flush()
    prop = Property(
        society_id=society.id, location_id=wing.id, house_number=house_number or f"A-{uuid.uuid4().hex[:4]}",
        house_type=HouseType.FLAT, floor_number=1, status=status,
    )
    db_session.add(prop)
    await db_session.commit()
    await db_session.refresh(prop)
    return prop


async def _seed_active_owner(db_session: AsyncSession, society: Society, prop: Property) -> User:
    owner = User(
        society_id=society.id, full_name="Existing Owner", mobile=f"9{uuid.uuid4().hex[:9]}", status=UserStatus.ACTIVE,
    )
    db_session.add(owner)
    await db_session.flush()
    db_session.add(UserRole(user_id=owner.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    db_session.add(
        PropertyResident(
            society_id=society.id, property_id=prop.id, resident_id=owner.id,
            relationship_type=RelationshipType.OWNER, is_active=True, start_date=date.today(),
            created_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()
    return owner


# --- Public property picker -------------------------------------------------


async def test_public_properties_lists_active_properties_unauthenticated(
    client: AsyncClient, db_session: AsyncSession
):
    society = await _seed_society(db_session)
    active_prop = await _seed_property(db_session, society, house_number="A-1")
    await _seed_property(db_session, society, house_number="A-2", status="INACTIVE")

    resp = await client.get(f"/api/v1/societies/{society.id}/properties/public")
    assert resp.status_code == 200
    house_numbers = [p["house_number"] for p in resp.json()]
    assert house_numbers == ["A-1"]
    assert resp.json()[0]["id"] == str(active_prop.id)


async def test_public_properties_empty_for_pending_society(client: AsyncClient, db_session: AsyncSession):
    society = await _seed_society(db_session, active=False)
    await _seed_property(db_session, society, house_number="A-1")

    resp = await client.get(f"/api/v1/societies/{society.id}/properties/public")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_public_properties_empty_for_unknown_society(client: AsyncClient, db_session: AsyncSession):
    resp = await client.get(f"/api/v1/societies/{uuid.uuid4()}/properties/public")
    assert resp.status_code == 200
    assert resp.json() == []


# --- Resident signup ---------------------------------------------------------


async def test_resident_signup_requires_property_id(client: AsyncClient, db_session: AsyncSession):
    society = await _seed_society(db_session)
    resp = await client.post(
        "/api/v1/residents/signup",
        json={"full_name": "New Resident", "mobile": "9830000001", "society_id": str(society.id)},
    )
    assert resp.status_code == 422


async def test_resident_signup_rejects_property_from_another_society(
    client: AsyncClient, db_session: AsyncSession
):
    society = await _seed_society(db_session)
    other_society = await _seed_society(db_session)
    other_prop = await _seed_property(db_session, other_society)

    resp = await client.post(
        "/api/v1/residents/signup",
        json={
            "full_name": "New Resident", "mobile": "9830000002", "society_id": str(society.id),
            "property_id": str(other_prop.id), "relationship_type": "OWNER",
        },
    )
    assert resp.status_code == 404


async def test_resident_signup_as_tenant_rejected_without_active_owner(
    client: AsyncClient, db_session: AsyncSession
):
    society = await _seed_society(db_session)
    prop = await _seed_property(db_session, society)

    resp = await client.post(
        "/api/v1/residents/signup",
        json={
            "full_name": "New Tenant", "mobile": "9830000003", "society_id": str(society.id),
            "property_id": str(prop.id), "relationship_type": "TENANT",
        },
    )
    assert resp.status_code == 409


async def test_resident_signup_as_tenant_succeeds_with_active_owner(
    client: AsyncClient, db_session: AsyncSession
):
    society = await _seed_society(db_session)
    prop = await _seed_property(db_session, society)
    await _seed_active_owner(db_session, society, prop)

    resp = await client.post(
        "/api/v1/residents/signup",
        json={
            "full_name": "New Tenant", "mobile": "9830000004", "society_id": str(society.id),
            "property_id": str(prop.id), "relationship_type": "TENANT",
        },
    )
    assert resp.status_code == 200
    tenant_id = uuid.UUID(resp.json()["id"])

    link = (
        await db_session.execute(select(PropertyResident).where(PropertyResident.resident_id == tenant_id))
    ).scalar_one()
    assert link.property_id == prop.id
    assert link.relationship_type == RelationshipType.TENANT
    assert link.is_active is True


async def test_resident_signup_link_created_immediately_but_inert_until_approved(
    client: AsyncClient, db_session: AsyncSession
):
    """Same pattern as Admin's own-unit signup capture — the link exists
    right away, but the account (and therefore anything gated on it) stays
    unusable until Admin approval."""
    society = await _seed_society(db_session)
    prop = await _seed_property(db_session, society)

    resp = await client.post(
        "/api/v1/residents/signup",
        json={
            "full_name": "New Owner", "mobile": "9830000005", "society_id": str(society.id),
            "property_id": str(prop.id), "relationship_type": "OWNER",
        },
    )
    resident_id = uuid.UUID(resp.json()["id"])

    link = (
        await db_session.execute(select(PropertyResident).where(PropertyResident.resident_id == resident_id))
    ).scalar_one()
    assert link.is_active is True

    from tests.conftest import auth_headers
    headers = auth_headers(resident_id, society.id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401  # PENDING account — not usable yet


# --- Admin signup: existing property alternative -----------------------------


async def test_admin_signup_with_existing_property_creates_link_and_resident_role(
    client: AsyncClient, db_session: AsyncSession
):
    society = await _seed_society(db_session)
    prop = await _seed_property(db_session, society)

    resp = await client.post(
        "/api/v1/admins/signup",
        json={
            "full_name": "Admin Who Lives Here Already", "mobile": "9830000010", "society_id": str(society.id),
            "existing_property_id": str(prop.id), "existing_property_relationship": "OWNER",
        },
    )
    assert resp.status_code == 200
    admin_id = uuid.UUID(resp.json()["id"])

    link = (
        await db_session.execute(select(PropertyResident).where(PropertyResident.resident_id == admin_id))
    ).scalar_one()
    assert link.property_id == prop.id
    assert link.relationship_type == RelationshipType.OWNER

    resident_role = (
        await db_session.execute(
            select(UserRole).where(
                UserRole.user_id == admin_id, UserRole.role == Role.RESIDENT, UserRole.revoked_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    assert resident_role is not None


async def test_admin_signup_existing_property_as_tenant_rejected_without_owner(
    client: AsyncClient, db_session: AsyncSession
):
    society = await _seed_society(db_session)
    prop = await _seed_property(db_session, society)

    resp = await client.post(
        "/api/v1/admins/signup",
        json={
            "full_name": "Admin Tenant", "mobile": "9830000011", "society_id": str(society.id),
            "existing_property_id": str(prop.id), "existing_property_relationship": "TENANT",
        },
    )
    assert resp.status_code == 409


async def test_admin_signup_rejects_partial_existing_property_fields(
    client: AsyncClient, db_session: AsyncSession
):
    society = await _seed_society(db_session)
    prop = await _seed_property(db_session, society)

    resp = await client.post(
        "/api/v1/admins/signup",
        json={
            "full_name": "Partial Admin", "mobile": "9830000013", "society_id": str(society.id),
            "existing_property_id": str(prop.id),  # relationship omitted
        },
    )
    assert resp.status_code == 422
