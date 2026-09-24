"""Amenity booking overlap prevention — Section 20.

create_booking previously had no check at all: two Residents could book
the exact same amenity/date/time slot, both landing PENDING, with no way
for the second Resident to know the slot was already taken until an Admin
eventually decided one of them (the bug this fixes). Also covers the new
GET /amenities/{id}/slots endpoint a Resident uses to see what's already
booked before submitting a request."""
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, RelationshipType, Role, UserStatus
from app.models.identity import Property, PropertyResident, SocietyLocation, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio

TOMORROW = date(2026, 9, 25).isoformat()


async def _seed_property_and_residents(db_session: AsyncSession, society_id, count: int = 2):
    loc = SocietyLocation(society_id=society_id, name="Wing A", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()
    prop = Property(
        society_id=society_id, location_id=loc.id, house_number="A-1",
        house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
    )
    db_session.add(prop)
    await db_session.flush()

    residents = []
    for i in range(count):
        r = User(society_id=society_id, full_name=f"Amenity Resident {i}", mobile=f"9310000{i:03d}", status=UserStatus.ACTIVE)
        db_session.add(r)
        await db_session.flush()
        db_session.add(UserRole(user_id=r.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
        db_session.add(
            PropertyResident(
                society_id=society_id, property_id=prop.id, resident_id=r.id,
                relationship_type=RelationshipType.OWNER, is_active=True, created_at=datetime.now(timezone.utc),
            )
        )
        residents.append(r)
    await db_session.commit()
    await db_session.refresh(prop)
    return prop, residents


async def test_overlapping_slot_is_rejected_with_409(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post("/api/v1/amenities", json={"name": "Clubhouse"}, headers=admin_headers)
    assert resp.status_code == 200
    amenity_id = resp.json()["id"]

    prop, residents = await _seed_property_and_residents(db_session, society_id, 2)
    first_headers = auth_headers(residents[0].id, society_id, Role.RESIDENT, [Role.RESIDENT])
    second_headers = auth_headers(residents[1].id, society_id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.post(
        "/api/v1/amenities/bookings",
        json={
            "amenity_id": amenity_id, "property_id": str(prop.id),
            "booking_date": TOMORROW, "start_time": "10:00:00", "end_time": "11:00:00",
        },
        headers=first_headers,
    )
    assert resp.status_code == 200

    # Second Resident tries to book a slot that overlaps (10:30–11:30).
    resp = await client.post(
        "/api/v1/amenities/bookings",
        json={
            "amenity_id": amenity_id, "property_id": str(prop.id),
            "booking_date": TOMORROW, "start_time": "10:30:00", "end_time": "11:30:00",
        },
        headers=second_headers,
    )
    assert resp.status_code == 409

    # A non-overlapping slot on the same date is still fine.
    resp = await client.post(
        "/api/v1/amenities/bookings",
        json={
            "amenity_id": amenity_id, "property_id": str(prop.id),
            "booking_date": TOMORROW, "start_time": "11:00:00", "end_time": "12:00:00",
        },
        headers=second_headers,
    )
    assert resp.status_code == 200


async def test_occupied_slots_endpoint_shows_taken_times_without_resident_identity(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post("/api/v1/amenities", json={"name": "Pool"}, headers=admin_headers)
    amenity_id = resp.json()["id"]

    prop, residents = await _seed_property_and_residents(db_session, society_id, 2)
    first_headers = auth_headers(residents[0].id, society_id, Role.RESIDENT, [Role.RESIDENT])
    second_headers = auth_headers(residents[1].id, society_id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.get(
        f"/api/v1/amenities/{amenity_id}/slots", params={"booking_date": TOMORROW}, headers=second_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await client.post(
        "/api/v1/amenities/bookings",
        json={
            "amenity_id": amenity_id, "property_id": str(prop.id),
            "booking_date": TOMORROW, "start_time": "09:00:00", "end_time": "10:00:00",
        },
        headers=first_headers,
    )
    assert resp.status_code == 200

    resp = await client.get(
        f"/api/v1/amenities/{amenity_id}/slots", params={"booking_date": TOMORROW}, headers=second_headers,
    )
    assert resp.status_code == 200
    slots = resp.json()
    assert len(slots) == 1
    assert slots[0]["start_time"] == "09:00:00"
    assert slots[0]["end_time"] == "10:00:00"
    assert slots[0]["status"] == "PENDING"
    assert "resident_id" not in slots[0]


async def test_two_pending_bookings_for_the_same_slot_cannot_both_be_approved(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Guards the race window (two requests landing before either is
    decided) that create_booking's own check can't cover by itself."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post("/api/v1/amenities", json={"name": "Hall"}, headers=admin_headers)
    amenity_id = resp.json()["id"]
    prop, residents = await _seed_property_and_residents(db_session, society_id, 2)
    first_headers = auth_headers(residents[0].id, society_id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.post(
        "/api/v1/amenities/bookings",
        json={
            "amenity_id": amenity_id, "property_id": str(prop.id),
            "booking_date": TOMORROW, "start_time": "14:00:00", "end_time": "15:00:00",
        },
        headers=first_headers,
    )
    booking_id = resp.json()["id"]

    # Simulate a second PENDING booking for the same slot having slipped in
    # (e.g. a concurrent request) by inserting it directly.
    from app.models.operations import Amenity, AmenityBooking
    from app.models.enums import BookingStatus
    from datetime import time as time_cls

    other = AmenityBooking(
        society_id=society_id, amenity_id=amenity_id, property_id=prop.id, resident_id=residents[1].id,
        booking_date=date(2026, 9, 25), start_time=time_cls(14, 0), end_time=time_cls(15, 0),
        status=BookingStatus.PENDING,
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    resp = await client.post(
        f"/api/v1/amenities/bookings/{booking_id}/decision", json={"approve": True}, headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED"

    resp = await client.post(
        f"/api/v1/amenities/bookings/{other.id}/decision", json={"approve": True}, headers=admin_headers,
    )
    assert resp.status_code == 409
