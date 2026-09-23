"""Society lifecycle tests — audit finding: PATCH /societies/{id}/status
accepted ANY SocietyStatus unconditionally, so a Platform Owner could send
PENDING at any time (ACTIVE -> PENDING, SUSPENDED -> PENDING) even though
PENDING is only supposed to be reachable via signup and only ever left via
POST /societies/{id}/approve."""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, SocietyStatus, UserStatus
from app.models.identity import Society, SocietyLocation, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_platform_owner(db_session: AsyncSession, mobile: str) -> User:
    owner = User(society_id=None, full_name="Platform Owner", mobile=mobile, status=UserStatus.ACTIVE)
    db_session.add(owner)
    await db_session.flush()
    db_session.add(UserRole(user_id=owner.id, role=Role.PLATFORM_OWNER, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    await db_session.refresh(owner)
    return owner


async def test_society_status_cannot_be_set_to_pending(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9700000001")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.patch(f"/api/v1/societies/{society_id}/status", json={"status": "PENDING"}, headers=headers)
    assert resp.status_code == 400

    society = (
        await db_session.execute(select(Society).where(Society.id == society_id))
    ).scalar_one()
    assert society.status == SocietyStatus.ACTIVE


async def test_pending_society_status_requires_approve_endpoint(
    client: AsyncClient, db_session: AsyncSession
):
    owner = await _seed_platform_owner(db_session, "9700000002")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    pending_society = Society(name="Pending Society", code="SOC-PENDING-1", status=SocietyStatus.PENDING)
    db_session.add(pending_society)
    await db_session.commit()
    await db_session.refresh(pending_society)

    # Trying to move it to SUSPENDED (or anything) via the generic status
    # endpoint before it's been approved must fail — /approve is the only
    # legitimate way out of PENDING.
    resp = await client.patch(
        f"/api/v1/societies/{pending_society.id}/status", json={"status": "SUSPENDED"}, headers=headers
    )
    assert resp.status_code == 409

    resp = await client.post(f"/api/v1/societies/{pending_society.id}/approve", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"


async def test_society_can_still_toggle_active_and_suspended(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9700000003")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.patch(f"/api/v1/societies/{society_id}/status", json={"status": "SUSPENDED"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUSPENDED"

    resp = await client.patch(f"/api/v1/societies/{society_id}/status", json={"status": "ACTIVE"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"


def _create_society_body(name: str, **overrides) -> dict:
    body = {"name": name, "address": "1 Main Rd", "city": "Pune", "state": "MH", "pincode": "411001"}
    body.update(overrides)
    return body


async def test_platform_owner_can_create_society_directly(
    client: AsyncClient, db_session: AsyncSession
):
    """New flow: a society is only ever created this way now — directly by
    the Platform Owner, ACTIVE immediately (no separate approval step,
    since creating it from their own dashboard IS the approval)."""
    owner = await _seed_platform_owner(db_session, "9700000004")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.post(
        "/api/v1/societies", json=_create_society_body("Green Meadows"), headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ACTIVE"
    assert body["name"] == "Green Meadows"
    assert body["code"]  # auto-generated, never blank


async def test_society_creation_requires_address_fields(client: AsyncClient, db_session: AsyncSession):
    """Every field except `locations` is required now — only the location
    list is optional (Section: Platform Owner society creation)."""
    owner = await _seed_platform_owner(db_session, "9700000010")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    body = _create_society_body("Incomplete Society")
    del body["city"]
    resp = await client.post("/api/v1/societies", json=body, headers=headers)
    assert resp.status_code == 422


async def test_society_code_is_auto_generated_and_unique_even_for_identical_names(
    client: AsyncClient, db_session: AsyncSession
):
    """No client can ever set/collide a code — two societies with the
    EXACT same name still get two different, auto-generated codes."""
    owner = await _seed_platform_owner(db_session, "9700000005")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    body = _create_society_body("Sunrise Apartments")
    resp1 = await client.post("/api/v1/societies", json=body, headers=headers)
    assert resp1.status_code == 200
    resp2 = await client.post("/api/v1/societies", json=body, headers=headers)
    assert resp2.status_code == 200

    assert resp1.json()["code"] != resp2.json()["code"]


async def test_society_creation_with_optional_locations(
    client: AsyncClient, db_session: AsyncSession
):
    """Locations are the one optional field — a Platform Owner can add one
    or more Wings/Rows right at creation, in the same request."""
    owner = await _seed_platform_owner(db_session, "9700000011")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    body = _create_society_body(
        "Society With Wings",
        locations=[{"name": "Wing A", "location_type": "WING"}, {"name": "Wing B", "location_type": "WING"}],
    )
    resp = await client.post("/api/v1/societies", json=body, headers=headers)
    assert resp.status_code == 200
    society_id = resp.json()["id"]

    locations = (
        await db_session.execute(select(SocietyLocation).where(SocietyLocation.society_id == uuid.UUID(society_id)))
    ).scalars().all()
    assert {loc.name for loc in locations} == {"Wing A", "Wing B"}


async def test_non_platform_owner_cannot_create_society(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    admin_id = two_societies_with_admins["a"]["admin_id"]
    society_id = two_societies_with_admins["a"]["society_id"]
    headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/societies", json=_create_society_body("Rogue Society"), headers=headers
    )
    assert resp.status_code == 403


async def test_platform_owner_can_edit_society_profile(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    original_code = (
        await db_session.execute(select(Society).where(Society.id == society_id))
    ).scalar_one().code
    owner = await _seed_platform_owner(db_session, "9700000012")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.patch(
        f"/api/v1/societies/{society_id}",
        json={"name": "Renamed Society", "address": "New Rd", "city": "Mumbai", "state": "MH", "pincode": "400001"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Renamed Society"
    assert body["city"] == "Mumbai"
    assert body["code"] == original_code  # code is immutable via this endpoint


async def test_non_platform_owner_cannot_edit_society_profile(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    admin_id = two_societies_with_admins["a"]["admin_id"]
    society_id = two_societies_with_admins["a"]["society_id"]
    headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.patch(
        f"/api/v1/societies/{society_id}",
        json={"name": "Hijacked", "address": "X", "city": "X", "state": "X", "pincode": "000000"},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_society_lookup_by_code_is_public_and_scoped_to_active(
    client: AsyncClient, db_session: AsyncSession
):
    """Used by the Admin/Resident signup forms — public (no auth), and
    only ever resolves an ACTIVE society."""
    owner = await _seed_platform_owner(db_session, "9700000006")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])
    resp = await client.post(
        "/api/v1/societies", json=_create_society_body("Lakeview Society"), headers=headers
    )
    society_id = resp.json()["id"]
    code = resp.json()["code"]

    resp = await client.get(f"/api/v1/societies/lookup/{code}")
    assert resp.status_code == 200
    assert resp.json() == {"id": society_id, "name": "Lakeview Society"}

    resp = await client.get("/api/v1/societies/lookup/SOC-DOES-NOT-EXIST")
    assert resp.status_code == 404

    # A PENDING society (old bundled signup flow) isn't found either.
    pending = Society(name="Pending One", code="SOC-PEND-LOOKUP", status=SocietyStatus.PENDING)
    db_session.add(pending)
    await db_session.commit()
    resp = await client.get("/api/v1/societies/lookup/SOC-PEND-LOOKUP")
    assert resp.status_code == 404


async def test_society_search_is_public_and_matches_by_name_substring(
    client: AsyncClient, db_session: AsyncSession
):
    """Search picker alternative to the code lookup — public, matches a
    substring of the name, only ACTIVE societies, and never leaks `code`."""
    owner = await _seed_platform_owner(db_session, "9700000007")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])
    resp = await client.post(
        "/api/v1/societies", json=_create_society_body("Palm Residency", city="Pune"), headers=headers
    )
    society_id = resp.json()["id"]

    resp = await client.get("/api/v1/societies/search", params={"q": "palm res"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0] == {"id": society_id, "name": "Palm Residency", "city": "Pune"}
    assert "code" not in body[0]

    # A PENDING society isn't searchable either — matches lookup's behavior.
    pending = Society(name="Pending Palms", code="SOC-PEND-PALMS", status=SocietyStatus.PENDING)
    db_session.add(pending)
    await db_session.commit()
    resp = await client.get("/api/v1/societies/search", params={"q": "pending palms"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_society_search_rejects_too_short_query(client: AsyncClient, db_session: AsyncSession):
    resp = await client.get("/api/v1/societies/search", params={"q": "ab"})
    assert resp.status_code == 400


async def test_society_search_is_rate_limited_per_ip(client: AsyncClient, db_session: AsyncSession):
    for _ in range(30):
        resp = await client.get("/api/v1/societies/search", params={"q": "nonexistent society"})
        assert resp.status_code == 200

    resp = await client.get("/api/v1/societies/search", params={"q": "nonexistent society"})
    assert resp.status_code == 429
