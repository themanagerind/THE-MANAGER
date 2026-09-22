"""Cross-society isolation tests — priority #2 per Section 42."""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, Role, UserStatus
from app.models.identity import Property, SocietyLocation, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


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
