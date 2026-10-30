"""Cross-society isolation tests — priority #2 per Section 42."""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, RelationshipType, Role, UserStatus
from app.models.identity import Property, PropertyResident, SocietyLocation, SubAdminScope, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_subadmin_scoped_to_wing_a(db_session: AsyncSession, society_id):
    """Two wings, a property in each, and a Sub-admin whose SubAdminScope
    only covers Wing A. Returns (subadmin, prop_in_a, prop_in_b)."""
    loc_a = SocietyLocation(society_id=society_id, name="Wing A", location_type=LocationType.WING)
    loc_b = SocietyLocation(society_id=society_id, name="Wing B", location_type=LocationType.WING)
    db_session.add_all([loc_a, loc_b])
    await db_session.flush()

    prop_in_a = Property(
        society_id=society_id, location_id=loc_a.id, house_number="A-101",
        house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
    )
    prop_in_b = Property(
        society_id=society_id, location_id=loc_b.id, house_number="B-101",
        house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
    )
    db_session.add_all([prop_in_a, prop_in_b])
    await db_session.flush()

    subadmin = User(society_id=society_id, full_name="SubAdmin", mobile="9100000009", status=UserStatus.ACTIVE)
    db_session.add(subadmin)
    await db_session.flush()
    db_session.add(UserRole(user_id=subadmin.id, role=Role.SUB_ADMIN, assigned_at=datetime.now(timezone.utc)))
    db_session.add(
        SubAdminScope(
            society_id=society_id, sub_admin_id=subadmin.id, location_id=loc_a.id,
            assigned_by=subadmin.id, assigned_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()
    await db_session.refresh(subadmin)
    await db_session.refresh(prop_in_a)
    await db_session.refresh(prop_in_b)
    return subadmin, prop_in_a, prop_in_b


async def _seed_location_and_property(db_session: AsyncSession, society_id):
    loc = SocietyLocation(society_id=society_id, name="Wing A", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()
    prop = Property(
        society_id=society_id, location_id=loc.id, house_number="101",
        house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
    )
    db_session.add(prop)
    await db_session.commit()
    await db_session.refresh(prop)
    return prop


async def test_admin_cannot_see_other_societys_properties(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    fixtures = two_societies_with_admins
    prop_a = await _seed_location_and_property(db_session, fixtures["a"]["society_id"])

    headers_b = auth_headers(fixtures["b"]["admin_id"], fixtures["b"]["society_id"], Role.ADMIN, [Role.ADMIN])
    resp = await client.get("/api/v1/properties", headers=headers_b)
    assert resp.status_code == 200
    returned_ids = {p["id"] for p in resp.json()}
    assert str(prop_a.id) not in returned_ids


async def test_admin_cannot_approve_resident_in_other_society(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    fixtures = two_societies_with_admins
    resident = User(
        society_id=fixtures["a"]["society_id"], full_name="Resident A", mobile="9100000001", status=UserStatus.PENDING,
    )
    db_session.add(resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    await db_session.refresh(resident)

    headers_b = auth_headers(fixtures["b"]["admin_id"], fixtures["b"]["society_id"], Role.ADMIN, [Role.ADMIN])
    resp = await client.post(
        f"/api/v1/residents/{resident.id}/approval", json={"approve": True}, headers=headers_b
    )
    assert resp.status_code == 404  # not found *in their society* — never leaks existence details


async def test_subadmin_scope_check_rejects_property_outside_scope(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    """Even a well-formed request from a legitimate Sub-admin in the RIGHT
    society, but for a property outside their assigned wing/row, must 403 —
    Section 27's non-negotiable server-side scope check."""
    society_id = two_societies_with_admins["a"]["society_id"]

    loc_a = SocietyLocation(society_id=society_id, name="Wing A", location_type=LocationType.WING)
    loc_b = SocietyLocation(society_id=society_id, name="Wing B", location_type=LocationType.WING)
    db_session.add_all([loc_a, loc_b])
    await db_session.flush()

    prop_in_b = Property(
        society_id=society_id, location_id=loc_b.id, house_number="B-101",
        house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
    )
    db_session.add(prop_in_b)
    await db_session.flush()

    from app.models.identity import SubAdminScope
    subadmin = User(society_id=society_id, full_name="SubAdmin", mobile="9100000002", status=UserStatus.ACTIVE)
    db_session.add(subadmin)
    await db_session.flush()
    db_session.add(UserRole(user_id=subadmin.id, role=Role.SUB_ADMIN, assigned_at=datetime.now(timezone.utc)))
    db_session.add(
        SubAdminScope(
            society_id=society_id, sub_admin_id=subadmin.id, location_id=loc_a.id,
            assigned_by=subadmin.id, assigned_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    from app.services.scope_service import subadmin_has_scope_over_property
    has_scope = await subadmin_has_scope_over_property(db_session, subadmin.id, prop_in_b.id, society_id)
    assert has_scope is False


async def test_scope_check_rejects_property_from_different_society(db_session: AsyncSession, two_societies_with_admins):
    """Defense-in-depth hardening: passing a property that legitimately
    belongs to a DIFFERENT society must never resolve to True, even if a
    Sub-admin happens to have a scope with a matching location_id (location
    UUIDs are never guessable/colliding in practice, but the explicit
    society_id check must still hold regardless)."""
    fixtures = two_societies_with_admins
    prop_a = await _seed_location_and_property(db_session, fixtures["a"]["society_id"])

    from app.services.scope_service import subadmin_has_scope_over_property
    has_scope = await subadmin_has_scope_over_property(
        db_session, fixtures["b"]["admin_id"], prop_a.id, fixtures["b"]["society_id"]
    )
    assert has_scope is False


async def test_suspended_society_blocks_existing_token(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Regression test — audit finding C1: get_current_user() only checked
    User.status, never Society.status. An Admin's JWT issued while their
    society was ACTIVE kept working after the Platform Owner suspended
    that society. Every protected request must be blocked once the
    society is suspended, not just new logins."""
    from app.models.enums import SocietyStatus
    from app.models.identity import Society

    fixtures = two_societies_with_admins
    admin_id = fixtures["a"]["admin_id"]
    society_id = fixtures["a"]["society_id"]

    headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    # Token works while the society is ACTIVE.
    resp = await client.get("/api/v1/properties", headers=headers)
    assert resp.status_code == 200

    society = (
        await db_session.execute(select(Society).where(Society.id == society_id))
    ).scalar_one()
    society.status = SocietyStatus.SUSPENDED
    await db_session.commit()

    # Same token, same headers — must now be rejected on every request,
    # not only at login.
    resp = await client.get("/api/v1/properties", headers=headers)
    assert resp.status_code == 403


async def test_subadmin_cannot_see_payments_and_dues_outside_scope(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Regression test: /payments, /payments/pending and
    /payments/maintenance-dues previously returned the WHOLE society to a
    Sub-admin, ignoring their assigned Wing/Row scope (Section 27) —
    unlike /payments/maintenance-dues/by-property/{id}, approve, reject and
    correct, which already enforced it."""
    from datetime import date
    from app.models.enums import MaintenanceDueStatus, PaymentMethod, PaymentStatus
    from app.models.payments import MaintenanceDue, Payment

    society_id = two_societies_with_admins["a"]["society_id"]
    subadmin, prop_in_a, prop_in_b = await _seed_subadmin_scoped_to_wing_a(db_session, society_id)

    resident = User(society_id=society_id, full_name="Resident", mobile="9100000010", status=UserStatus.ACTIVE)
    db_session.add(resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    await db_session.flush()

    now = datetime.now(timezone.utc)
    due_a = MaintenanceDue(
        society_id=society_id, property_id=prop_in_a.id, amount=1000.0, due_date=date.today(),
        status=MaintenanceDueStatus.PENDING, billing_month=date.today().replace(day=1),
        generated_at=now, updated_at=now,
    )
    due_b = MaintenanceDue(
        society_id=society_id, property_id=prop_in_b.id, amount=2000.0, due_date=date.today(),
        status=MaintenanceDueStatus.PENDING, billing_month=date.today().replace(day=1),
        generated_at=now, updated_at=now,
    )
    db_session.add_all([due_a, due_b])
    await db_session.flush()

    payment_a = Payment(
        society_id=society_id, maintenance_due_id=due_a.id, property_id=prop_in_a.id,
        resident_id=resident.id, payment_method=PaymentMethod.MANUAL_UPI, amount=1000.0,
        status=PaymentStatus.PENDING_APPROVAL, idempotency_key=uuid.uuid4(),
    )
    payment_b = Payment(
        society_id=society_id, maintenance_due_id=due_b.id, property_id=prop_in_b.id,
        resident_id=resident.id, payment_method=PaymentMethod.MANUAL_UPI, amount=2000.0,
        status=PaymentStatus.PENDING_APPROVAL, idempotency_key=uuid.uuid4(),
    )
    db_session.add_all([payment_a, payment_b])
    await db_session.commit()

    headers = auth_headers(subadmin.id, society_id, Role.SUB_ADMIN, [Role.SUB_ADMIN])

    resp = await client.get("/api/v1/payments/maintenance-dues", headers=headers)
    assert resp.status_code == 200
    due_property_ids = {d["property_id"] for d in resp.json()}
    assert str(prop_in_a.id) in due_property_ids
    assert str(prop_in_b.id) not in due_property_ids

    resp = await client.get("/api/v1/payments", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    payment_property_ids = {p["property_id"] for p in body["items"]}
    assert str(prop_in_a.id) in payment_property_ids
    assert str(prop_in_b.id) not in payment_property_ids
    assert body["total"] == 1  # scoped total, not the whole society's 2

    resp = await client.get("/api/v1/payments/pending", headers=headers)
    assert resp.status_code == 200
    pending_property_ids = {p["property_id"] for p in resp.json()}
    assert str(prop_in_a.id) in pending_property_ids
    assert str(prop_in_b.id) not in pending_property_ids


async def test_subadmin_cannot_list_residents_of_property_outside_scope(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    subadmin, prop_in_a, prop_in_b = await _seed_subadmin_scoped_to_wing_a(db_session, society_id)
    headers = auth_headers(subadmin.id, society_id, Role.SUB_ADMIN, [Role.SUB_ADMIN])

    resp = await client.get(f"/api/v1/residents/by-property/{prop_in_a.id}", headers=headers)
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/residents/by-property/{prop_in_b.id}", headers=headers)
    assert resp.status_code == 403


async def test_subadmin_only_sees_residents_property_links_within_scope(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """A Resident linked to properties in two different wings — a
    scope-restricted Sub-admin should only see the link inside their scope,
    not silently the whole list either."""
    society_id = two_societies_with_admins["a"]["society_id"]
    subadmin, prop_in_a, prop_in_b = await _seed_subadmin_scoped_to_wing_a(db_session, society_id)

    resident = User(society_id=society_id, full_name="Resident", mobile="9100000011", status=UserStatus.ACTIVE)
    db_session.add(resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    now = datetime.now(timezone.utc)
    db_session.add(
        PropertyResident(
            society_id=society_id, property_id=prop_in_a.id, resident_id=resident.id,
            relationship_type=RelationshipType.OWNER, is_active=True, created_at=now,
        )
    )
    db_session.add(
        PropertyResident(
            society_id=society_id, property_id=prop_in_b.id, resident_id=resident.id,
            relationship_type=RelationshipType.OWNER, is_active=True, created_at=now,
        )
    )
    await db_session.commit()

    headers = auth_headers(subadmin.id, society_id, Role.SUB_ADMIN, [Role.SUB_ADMIN])
    resp = await client.get(f"/api/v1/residents/{resident.id}/properties", headers=headers)
    assert resp.status_code == 200
    linked_property_ids = {link["property_id"] for link in resp.json()}
    assert linked_property_ids == {str(prop_in_a.id)}


async def test_subadmin_cannot_see_amenity_bookings_outside_scope(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Audit fix: GET /amenities/bookings only branched on RESIDENT vs.
    everyone-else, so a Sub-admin fell into the same unfiltered branch as
    Admin and could read every booking (and its resident_id/property_id)
    society-wide — decide_booking's write path was already scope-checked,
    but this read wasn't (same bug class as the payments one above,
    test_subadmin_cannot_see_payments_and_dues_outside_scope)."""
    from datetime import date, time
    from app.models.operations import Amenity, AmenityBooking

    society_id = two_societies_with_admins["a"]["society_id"]
    subadmin, prop_in_a, prop_in_b = await _seed_subadmin_scoped_to_wing_a(db_session, society_id)

    resident = User(society_id=society_id, full_name="Resident", mobile="9100000012", status=UserStatus.ACTIVE)
    db_session.add(resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))

    amenity = Amenity(society_id=society_id, name="Clubhouse", is_active=True)
    db_session.add(amenity)
    await db_session.flush()

    booking_a = AmenityBooking(
        society_id=society_id, amenity_id=amenity.id, property_id=prop_in_a.id, resident_id=resident.id,
        booking_date=date.today(), start_time=time(10, 0), end_time=time(11, 0), status="PENDING",
    )
    booking_b = AmenityBooking(
        society_id=society_id, amenity_id=amenity.id, property_id=prop_in_b.id, resident_id=resident.id,
        booking_date=date.today(), start_time=time(12, 0), end_time=time(13, 0), status="PENDING",
    )
    db_session.add_all([booking_a, booking_b])
    await db_session.commit()

    headers = auth_headers(subadmin.id, society_id, Role.SUB_ADMIN, [Role.SUB_ADMIN])
    resp = await client.get("/api/v1/amenities/bookings", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    booking_property_ids = {b["property_id"] for b in body["items"]}
    assert str(prop_in_a.id) in booking_property_ids
    assert str(prop_in_b.id) not in booking_property_ids
    assert body["total"] == 1  # scoped total, not the whole society's 2
