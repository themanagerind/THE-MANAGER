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
from app.models.identity import Property, Society, SocietyLocation, User, UserRole
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


async def test_society_creation_with_optional_gps_location(
    client: AsyncClient, db_session: AsyncSession
):
    """`latitude`/`longitude` are optional too, same as `locations` — a
    Platform Owner can pin the society's GPS location right at creation."""
    owner = await _seed_platform_owner(db_session, "9700000024")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    body = _create_society_body("Hillview Society", latitude=19.0760, longitude=72.8777)
    resp = await client.post("/api/v1/societies", json=body, headers=headers)
    assert resp.status_code == 200
    result = resp.json()
    assert result["latitude"] == 19.0760
    assert result["longitude"] == 72.8777


async def test_society_creation_without_gps_location_leaves_it_null(
    client: AsyncClient, db_session: AsyncSession
):
    owner = await _seed_platform_owner(db_session, "9700000025")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.post("/api/v1/societies", json=_create_society_body("No GPS Society"), headers=headers)
    assert resp.status_code == 200
    assert resp.json()["latitude"] is None
    assert resp.json()["longitude"] is None


async def test_society_creation_rejects_a_lone_gps_coordinate(
    client: AsyncClient, db_session: AsyncSession
):
    owner = await _seed_platform_owner(db_session, "9700000026")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    body = _create_society_body("Lone Coordinate Society", latitude=19.0760)
    resp = await client.post("/api/v1/societies", json=body, headers=headers)
    assert resp.status_code == 422


async def test_society_creation_rejects_out_of_range_gps_coordinates(
    client: AsyncClient, db_session: AsyncSession
):
    owner = await _seed_platform_owner(db_session, "9700000027")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    body = _create_society_body("Bad GPS Society", latitude=200.0, longitude=72.8777)
    resp = await client.post("/api/v1/societies", json=body, headers=headers)
    assert resp.status_code == 422


async def test_platform_owner_can_set_and_clear_society_gps_location(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9700000028")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.patch(
        f"/api/v1/societies/{society_id}",
        json={
            "name": "Society A", "address": "1 Main Rd", "city": "Pune", "state": "MH", "pincode": "411001",
            "latitude": 18.5204, "longitude": 73.8567,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["latitude"] == 18.5204
    assert resp.json()["longitude"] == 73.8567

    # Sending neither clears a GPS pin already on record.
    resp = await client.patch(
        f"/api/v1/societies/{society_id}",
        json={"name": "Society A", "address": "1 Main Rd", "city": "Pune", "state": "MH", "pincode": "411001"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["latitude"] is None
    assert resp.json()["longitude"] is None


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


async def test_platform_owner_can_list_and_add_society_locations(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """The Societies page's Edit modal — a Platform Owner can view and add
    Wings/Rows for any society directly, without switching into that
    society's Admin role."""
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9700000013")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.get(f"/api/v1/societies/{society_id}/locations", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await client.post(
        f"/api/v1/societies/{society_id}/locations",
        json={"name": "Wing A", "location_type": "WING"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Wing A"

    resp = await client.get(f"/api/v1/societies/{society_id}/locations", headers=headers)
    assert resp.status_code == 200
    assert [loc["name"] for loc in resp.json()] == ["Wing A"]


async def test_society_locations_404_for_unknown_society(client: AsyncClient, db_session: AsyncSession):
    owner = await _seed_platform_owner(db_session, "9700000014")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.get(f"/api/v1/societies/{uuid.uuid4()}/locations", headers=headers)
    assert resp.status_code == 404

    resp = await client.post(
        f"/api/v1/societies/{uuid.uuid4()}/locations",
        json={"name": "Wing A", "location_type": "WING"},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_non_platform_owner_cannot_add_society_location(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    admin_id = two_societies_with_admins["a"]["admin_id"]
    society_id = two_societies_with_admins["a"]["society_id"]
    headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        f"/api/v1/societies/{society_id}/locations",
        json={"name": "Wing A", "location_type": "WING"},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_platform_owner_can_rename_and_retype_an_unused_location(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9700000021")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.post(
        f"/api/v1/societies/{society_id}/locations",
        json={"name": "Wing A", "location_type": "WING"},
        headers=headers,
    )
    location_id = resp.json()["id"]

    # Renaming is always fine.
    resp = await client.patch(
        f"/api/v1/societies/{society_id}/locations/{location_id}",
        json={"name": "Wing A1", "location_type": "WING"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Wing A1"

    # No Property points at it yet, so WING -> ROW is fine too.
    resp = await client.patch(
        f"/api/v1/societies/{society_id}/locations/{location_id}",
        json={"name": "Row A1", "location_type": "ROW"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Row A1"
    assert body["location_type"] == "ROW"


async def test_platform_owner_cannot_retype_a_location_already_in_use(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """A Wing already holding FLATs can't silently become a Row — nothing
    in the DB would catch existing properties ending up under the wrong
    location_type."""
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9700000022")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.post(
        f"/api/v1/societies/{society_id}/structure/flats",
        json={"wings": [{"floor_count": 1, "flats_per_floor": 1}]},
        headers=headers,
    )
    location_id = resp.json()[0]["location_id"]

    resp = await client.patch(
        f"/api/v1/societies/{society_id}/locations/{location_id}",
        json={"name": "Tower 1", "location_type": "ROW"},
        headers=headers,
    )
    assert resp.status_code == 409

    # Renaming without changing the type still works even while in use.
    resp = await client.patch(
        f"/api/v1/societies/{society_id}/locations/{location_id}",
        json={"name": "Tower One", "location_type": "WING"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Tower One"


async def test_location_edit_404_for_unknown_location(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9700000023")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.patch(
        f"/api/v1/societies/{society_id}/locations/{uuid.uuid4()}",
        json={"name": "Wing A", "location_type": "WING"},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_non_platform_owner_cannot_edit_society_location(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    admin_id = two_societies_with_admins["a"]["admin_id"]
    society_id = two_societies_with_admins["a"]["society_id"]
    headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.patch(
        f"/api/v1/societies/{society_id}/locations/{uuid.uuid4()}",
        json={"name": "Wing A", "location_type": "WING"},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_platform_owner_can_generate_flats_structure_with_per_wing_shape(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Bulk-generates every tower/floor/flat combination in one request —
    each Wing can have its own floor count and flats/floor (a taller
    tower next to a shorter one), and a Wing can be given a custom name;
    one left blank falls back to an auto-generated "Tower N"."""
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9700000015")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.post(
        f"/api/v1/societies/{society_id}/structure/flats",
        json={
            "wings": [
                {"name": "Sunrise Tower", "floor_count": 3, "flats_per_floor": 2},  # 6 flats
                {"floor_count": 2, "flats_per_floor": 3},  # 6 flats, name auto-generated
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 200
    properties = resp.json()
    assert len(properties) == 12
    assert all(p["house_type"] == "FLAT" for p in properties)
    assert all(p["floor_number"] is not None for p in properties)
    assert all(p["floors_above_ground"] == 0 for p in properties)
    assert len({p["house_number"] for p in properties}) == 12  # all unique

    locations = (
        await db_session.execute(select(SocietyLocation).where(SocietyLocation.society_id == society_id))
    ).scalars().all()
    assert {loc.name for loc in locations} == {"Sunrise Tower", "Tower 2"}
    assert all(loc.location_type == "WING" for loc in locations)


async def test_generate_flats_structure_rejects_total_over_cap(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9700000029")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.post(
        f"/api/v1/societies/{society_id}/structure/flats",
        json={"wings": [{"floor_count": 100, "flats_per_floor": 50} for _ in range(2)]},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_platform_owner_can_generate_bungalow_structure_and_set_floors(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Bulk-generates rows/houses (all starting at ground-floor-only), then
    the per-house follow-up step: setting how many storeys a specific
    house has above its (always-implied) ground floor."""
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9700000016")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.post(
        f"/api/v1/societies/{society_id}/structure/bungalows",
        json={"row_count": 2, "houses_per_row": 3},
        headers=headers,
    )
    assert resp.status_code == 200
    properties = resp.json()
    assert len(properties) == 6
    assert all(p["house_type"] == "BUNGALOW" for p in properties)
    assert all(p["floor_number"] is None for p in properties)
    assert all(p["floors_above_ground"] == 0 for p in properties)

    locations = (
        await db_session.execute(select(SocietyLocation).where(SocietyLocation.society_id == society_id))
    ).scalars().all()
    assert {loc.name for loc in locations} == {"Row 1", "Row 2"}
    assert all(loc.location_type == "ROW" for loc in locations)

    house_id = properties[0]["id"]
    resp = await client.patch(
        f"/api/v1/societies/{society_id}/properties/{house_id}/floors",
        json={"floors_above_ground": 2},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["floors_above_ground"] == 2

    prop = (await db_session.execute(select(Property).where(Property.id == uuid.UUID(house_id)))).scalar_one()
    assert prop.floors_above_ground == 2


async def test_floors_above_ground_rejected_for_flat_house(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9700000017")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.post(
        f"/api/v1/societies/{society_id}/structure/flats",
        json={"wings": [{"floor_count": 1, "flats_per_floor": 1}]},
        headers=headers,
    )
    flat_id = resp.json()[0]["id"]

    resp = await client.patch(
        f"/api/v1/societies/{society_id}/properties/{flat_id}/floors",
        json={"floors_above_ground": 1},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_generate_structure_rejects_out_of_bounds_counts(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9700000018")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.post(
        f"/api/v1/societies/{society_id}/structure/flats",
        json={"wings": [{"floor_count": 0, "flats_per_floor": 1}]},
        headers=headers,
    )
    assert resp.status_code == 422

    resp = await client.post(
        f"/api/v1/societies/{society_id}/structure/flats",
        json={"wings": []},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_generate_structure_404_for_unknown_society(client: AsyncClient, db_session: AsyncSession):
    owner = await _seed_platform_owner(db_session, "9700000019")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    resp = await client.post(
        f"/api/v1/societies/{uuid.uuid4()}/structure/flats",
        json={"wings": [{"floor_count": 1, "flats_per_floor": 1}]},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_non_platform_owner_cannot_generate_structure(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    admin_id = two_societies_with_admins["a"]["admin_id"]
    society_id = two_societies_with_admins["a"]["society_id"]
    headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        f"/api/v1/societies/{society_id}/structure/flats",
        json={"wings": [{"floor_count": 1, "flats_per_floor": 1}]},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_platform_owner_can_list_society_properties(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9700000020")
    headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    await client.post(
        f"/api/v1/societies/{society_id}/structure/bungalows",
        json={"row_count": 1, "houses_per_row": 2},
        headers=headers,
    )
    resp = await client.get(f"/api/v1/societies/{society_id}/properties", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


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
