"""Resident self-signup hardening tests — audit finding: POST
/residents/signup (public, unauthenticated) had no rate limiting, no check
that society_id refers to a real/ACTIVE society, and a duplicate
(society_id, mobile) signup surfaced as an unhandled 500 instead of a
clean error.

Also covers the self-service property link now required at signup (the
Resident picks their own house instead of an Admin linking it manually
after approval) — see test_signup_property_link.py for the fuller set of
property-link-specific cases (Tenant-needs-an-Owner, wrong society, etc)."""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, SocietyStatus
from app.models.identity import Property, Society, SocietyLocation

pytestmark = pytest.mark.asyncio


async def _seed_active_society_with_property(db_session: AsyncSession) -> tuple[Society, Property]:
    society = Society(name="Signup Test Society", code=f"SOC-SIGNUP-{uuid.uuid4().hex[:6]}", status=SocietyStatus.ACTIVE)
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


async def test_signup_rejects_nonexistent_society(client: AsyncClient, db_session: AsyncSession):
    resp = await client.post(
        "/api/v1/residents/signup",
        json={
            "full_name": "New Resident", "mobile": "9800000001", "society_id": str(uuid.uuid4()),
            "property_id": str(uuid.uuid4()), "relationship_type": "OWNER",
        },
    )
    assert resp.status_code == 404


async def test_signup_rejects_non_active_society(client: AsyncClient, db_session: AsyncSession):
    pending_society = Society(name="Pending Society", code=f"SOC-PENDING-{uuid.uuid4().hex[:6]}", status=SocietyStatus.PENDING)
    db_session.add(pending_society)
    await db_session.commit()
    await db_session.refresh(pending_society)

    resp = await client.post(
        "/api/v1/residents/signup",
        json={
            "full_name": "New Resident", "mobile": "9800000002", "society_id": str(pending_society.id),
            "property_id": str(uuid.uuid4()), "relationship_type": "OWNER",
        },
    )
    assert resp.status_code == 409


async def test_signup_succeeds_for_active_society(client: AsyncClient, db_session: AsyncSession):
    society, prop = await _seed_active_society_with_property(db_session)
    resp = await client.post(
        "/api/v1/residents/signup",
        json={
            "full_name": "New Resident", "mobile": "9800000003", "society_id": str(society.id),
            "property_id": str(prop.id), "relationship_type": "OWNER",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PENDING"


async def test_duplicate_signup_returns_clean_conflict_not_500(client: AsyncClient, db_session: AsyncSession):
    society, prop = await _seed_active_society_with_property(db_session)
    body = {
        "full_name": "New Resident", "mobile": "9800000004", "society_id": str(society.id),
        "property_id": str(prop.id), "relationship_type": "OWNER",
    }

    resp1 = await client.post("/api/v1/residents/signup", json=body)
    assert resp1.status_code == 200

    resp2 = await client.post("/api/v1/residents/signup", json=body)
    assert resp2.status_code == 409


async def test_signup_is_rate_limited_per_mobile(client: AsyncClient, db_session: AsyncSession):
    mobile = "9800000005"
    seeded = [await _seed_active_society_with_property(db_session) for _ in range(7)]

    responses = []
    for society, prop in seeded:
        resp = await client.post(
            "/api/v1/residents/signup",
            json={
                "full_name": "New Resident", "mobile": mobile, "society_id": str(society.id),
                "property_id": str(prop.id), "relationship_type": "OWNER",
            },
        )
        responses.append(resp.status_code)

    assert 429 in responses
