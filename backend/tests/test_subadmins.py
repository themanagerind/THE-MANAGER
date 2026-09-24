"""Sub-admin promotion — Admin promotes an ACTIVE Resident to Sub-admin of
one or more Wings/Rows (Section 6/7). No prior test coverage existed for
subadmin_service/router at all; added here alongside wiring the first real
UI on top of it (Admin's Residents page)."""
import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, RelationshipType, Role, SocietyStatus, UserStatus
from app.models.identity import Property, PropertyResident, Society, SocietyLocation, SubAdminScope, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_admin_and_resident(db_session: AsyncSession) -> dict:
    society = Society(name="Subadmin Test Society", code=f"SOC-SUBADM-{uuid.uuid4().hex[:6]}", status=SocietyStatus.ACTIVE)
    db_session.add(society)
    await db_session.flush()

    wing_a = SocietyLocation(society_id=society.id, name="Wing A", location_type=LocationType.WING)
    wing_b = SocietyLocation(society_id=society.id, name="Wing B", location_type=LocationType.WING)
    db_session.add_all([wing_a, wing_b])
    await db_session.flush()

    admin = User(society_id=society.id, full_name="Admin", mobile="9850000001", status=UserStatus.ACTIVE)
    resident = User(society_id=society.id, full_name="Resident One", mobile="9850000002", status=UserStatus.ACTIVE)
    pending_resident = User(society_id=society.id, full_name="Pending Resident", mobile="9850000003", status=UserStatus.PENDING)
    db_session.add_all([admin, resident, pending_resident])
    await db_session.flush()

    db_session.add_all([
        UserRole(user_id=admin.id, role=Role.ADMIN, assigned_at=datetime.now(timezone.utc)),
        UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)),
        UserRole(user_id=pending_resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)),
    ])
    await db_session.commit()

    return {
        "society": society, "wing_a": wing_a, "wing_b": wing_b,
        "admin": admin, "resident": resident, "pending_resident": pending_resident,
    }


# --- GET /residents (Admin's resident directory) ----------------------------


async def test_list_residents_defaults_to_every_status(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed_admin_and_resident(db_session)
    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])

    resp = await client.get("/api/v1/residents", headers=headers)
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()}
    assert str(seeded["resident"].id) in ids
    assert str(seeded["pending_resident"].id) in ids
    assert str(seeded["admin"].id) not in ids  # ADMIN role only, no RESIDENT role


async def test_list_residents_filters_by_status(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed_admin_and_resident(db_session)
    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])

    resp = await client.get("/api/v1/residents", params={"status": "ACTIVE"}, headers=headers)
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()}
    assert ids == {str(seeded["resident"].id)}


async def test_list_residents_requires_admin(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed_admin_and_resident(db_session)
    headers = auth_headers(seeded["resident"].id, seeded["society"].id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.get("/api/v1/residents", headers=headers)
    assert resp.status_code == 403


# --- POST /subadmins/promote -------------------------------------------------


async def test_admin_can_promote_active_resident_to_subadmin(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed_admin_and_resident(db_session)
    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(seeded["resident"].id), "location_ids": [str(seeded["wing_a"].id)]},
        headers=headers,
    )
    assert resp.status_code == 200
    scopes = resp.json()
    assert len(scopes) == 1
    assert scopes[0]["location_id"] == str(seeded["wing_a"].id)

    role = (
        await db_session.execute(
            select(UserRole).where(
                UserRole.user_id == seeded["resident"].id, UserRole.role == Role.SUB_ADMIN, UserRole.revoked_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    assert role is not None

    # Dual-role — RESIDENT role untouched.
    resident_role = (
        await db_session.execute(
            select(UserRole).where(
                UserRole.user_id == seeded["resident"].id, UserRole.role == Role.RESIDENT, UserRole.revoked_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    assert resident_role is not None


async def test_list_all_assignments_returns_active_scopes_with_names(client: AsyncClient, db_session: AsyncSession):
    """Assign Sub-admin page's "Current Sub-admins" overview — denormalized
    resident/location names in one call, revoked scopes excluded."""
    seeded = await _seed_admin_and_resident(db_session)
    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(seeded["resident"].id), "location_ids": [str(seeded["wing_a"].id)]},
        headers=headers,
    )
    scope_id = resp.json()[0]["id"]

    resp = await client.get("/api/v1/subadmins", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["scope_id"] == scope_id
    assert rows[0]["sub_admin_name"] == "Resident One"
    assert rows[0]["location_name"] == "Wing A"
    assert rows[0]["location_type"] == "WING"

    # Revoking drops it from the overview.
    resp = await client.delete(f"/api/v1/subadmins/scopes/{scope_id}", headers=headers)
    assert resp.status_code == 200
    resp = await client.get("/api/v1/subadmins", headers=headers)
    assert resp.json() == []


async def test_list_by_location_returns_only_residents_of_that_wing(client: AsyncClient, db_session: AsyncSession):
    """The Assign Sub-admin picker's residents list — someone linked to a
    property in a DIFFERENT Wing doesn't show up."""
    seeded = await _seed_admin_and_resident(db_session)
    prop_a = Property(
        society_id=seeded["society"].id, location_id=seeded["wing_a"].id, house_number="A-1",
        house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
    )
    prop_b = Property(
        society_id=seeded["society"].id, location_id=seeded["wing_b"].id, house_number="B-1",
        house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
    )
    db_session.add_all([prop_a, prop_b])
    await db_session.flush()

    other_resident = User(society_id=seeded["society"].id, full_name="Resident Two", mobile="9850000004", status=UserStatus.ACTIVE)
    db_session.add(other_resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=other_resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    db_session.add_all([
        PropertyResident(
            society_id=seeded["society"].id, property_id=prop_a.id, resident_id=seeded["resident"].id,
            relationship_type=RelationshipType.OWNER, is_active=True, start_date=date.today(),
            created_at=datetime.now(timezone.utc),
        ),
        PropertyResident(
            society_id=seeded["society"].id, property_id=prop_b.id, resident_id=other_resident.id,
            relationship_type=RelationshipType.OWNER, is_active=True, start_date=date.today(),
            created_at=datetime.now(timezone.utc),
        ),
    ])
    await db_session.commit()

    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])
    resp = await client.get(f"/api/v1/residents/by-location/{seeded['wing_a'].id}", headers=headers)
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()}
    assert ids == {str(seeded["resident"].id)}


async def test_admin_can_promote_with_multiple_locations(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed_admin_and_resident(db_session)
    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/subadmins/promote",
        json={
            "resident_id": str(seeded["resident"].id),
            "location_ids": [str(seeded["wing_a"].id), str(seeded["wing_b"].id)],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_promote_rejects_wing_already_scoped_to_another_subadmin(client: AsyncClient, db_session: AsyncSession):
    """Section 7: at most one active Sub-admin per Wing/Row."""
    seeded = await _seed_admin_and_resident(db_session)
    resident_2 = User(society_id=seeded["society"].id, full_name="Resident Two", mobile="9850000010", status=UserStatus.ACTIVE)
    db_session.add(resident_2)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident_2.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()

    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])
    resp = await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(seeded["resident"].id), "location_ids": [str(seeded["wing_a"].id)]},
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(resident_2.id), "location_ids": [str(seeded["wing_a"].id)]},
        headers=headers,
    )
    assert resp.status_code == 409

    # Only the first Sub-admin's scope exists.
    resp = await client.get(f"/api/v1/subadmins/{resident_2.id}/scopes", headers=headers)
    assert resp.json() == []


async def test_promote_rejects_if_only_one_of_several_wings_is_taken(client: AsyncClient, db_session: AsyncSession):
    """A partial conflict blocks the whole request — no half-applied
    promotion with only the uncontested Wing assigned."""
    seeded = await _seed_admin_and_resident(db_session)
    resident_2 = User(society_id=seeded["society"].id, full_name="Resident Two", mobile="9850000011", status=UserStatus.ACTIVE)
    db_session.add(resident_2)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident_2.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()

    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])
    await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(seeded["resident"].id), "location_ids": [str(seeded["wing_a"].id)]},
        headers=headers,
    )

    resp = await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(resident_2.id), "location_ids": [str(seeded["wing_b"].id), str(seeded["wing_a"].id)]},
        headers=headers,
    )
    assert resp.status_code == 409

    resp = await client.get(f"/api/v1/subadmins/{resident_2.id}/scopes", headers=headers)
    assert resp.json() == []  # Wing B wasn't assigned either


async def test_promote_allows_reassigning_a_wing_after_the_old_subadmin_is_demoted(
    client: AsyncClient, db_session: AsyncSession
):
    seeded = await _seed_admin_and_resident(db_session)
    resident_2 = User(society_id=seeded["society"].id, full_name="Resident Two", mobile="9850000012", status=UserStatus.ACTIVE)
    db_session.add(resident_2)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident_2.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()

    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])
    await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(seeded["resident"].id), "location_ids": [str(seeded["wing_a"].id)]},
        headers=headers,
    )
    resp = await client.delete(f"/api/v1/subadmins/{seeded['resident'].id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(resident_2.id), "location_ids": [str(seeded["wing_a"].id)]},
        headers=headers,
    )
    assert resp.status_code == 200


async def test_assign_additional_scope_rejects_wing_already_scoped_to_another_subadmin(
    client: AsyncClient, db_session: AsyncSession
):
    seeded = await _seed_admin_and_resident(db_session)
    resident_2 = User(society_id=seeded["society"].id, full_name="Resident Two", mobile="9850000013", status=UserStatus.ACTIVE)
    db_session.add(resident_2)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident_2.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()

    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])
    await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(seeded["resident"].id), "location_ids": [str(seeded["wing_a"].id)]},
        headers=headers,
    )
    await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(resident_2.id), "location_ids": [str(seeded["wing_b"].id)]},
        headers=headers,
    )

    resp = await client.post(
        f"/api/v1/subadmins/{resident_2.id}/scopes",
        json={"location_id": str(seeded["wing_a"].id)},
        headers=headers,
    )
    assert resp.status_code == 409


async def test_promote_rejects_pending_resident(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed_admin_and_resident(db_session)
    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(seeded["pending_resident"].id), "location_ids": [str(seeded["wing_a"].id)]},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_promote_rejects_location_from_another_society(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed_admin_and_resident(db_session)
    other = await _seed_admin_and_resident(db_session)
    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(seeded["resident"].id), "location_ids": [str(other["wing_a"].id)]},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_promote_requires_admin(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed_admin_and_resident(db_session)
    headers = auth_headers(seeded["resident"].id, seeded["society"].id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(seeded["resident"].id), "location_ids": [str(seeded["wing_a"].id)]},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_promoting_again_adds_scope_without_duplicating_role(client: AsyncClient, db_session: AsyncSession):
    """Re-running promote (e.g. to add a second Wing later) must not create
    a second SUB_ADMIN role row — just another scope."""
    seeded = await _seed_admin_and_resident(db_session)
    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])

    resp1 = await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(seeded["resident"].id), "location_ids": [str(seeded["wing_a"].id)]},
        headers=headers,
    )
    assert resp1.status_code == 200

    resp2 = await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(seeded["resident"].id), "location_ids": [str(seeded["wing_b"].id)]},
        headers=headers,
    )
    assert resp2.status_code == 200

    roles = (
        await db_session.execute(
            select(UserRole).where(
                UserRole.user_id == seeded["resident"].id, UserRole.role == Role.SUB_ADMIN, UserRole.revoked_at.is_(None)
            )
        )
    ).scalars().all()
    assert len(roles) == 1

    scopes = (
        await db_session.execute(
            select(SubAdminScope).where(
                SubAdminScope.sub_admin_id == seeded["resident"].id, SubAdminScope.revoked_at.is_(None)
            )
        )
    ).scalars().all()
    assert len(scopes) == 2


# --- GET /subadmins/{id}/scopes, DELETE /subadmins/scopes/{id} --------------


async def test_admin_can_list_and_revoke_scope(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed_admin_and_resident(db_session)
    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(seeded["resident"].id), "location_ids": [str(seeded["wing_a"].id)]},
        headers=headers,
    )
    scope_id = resp.json()[0]["id"]

    resp = await client.get(f"/api/v1/subadmins/{seeded['resident'].id}/scopes", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = await client.delete(f"/api/v1/subadmins/scopes/{scope_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["revoked_at"] is not None

    resp = await client.get(f"/api/v1/subadmins/{seeded['resident'].id}/scopes", headers=headers)
    assert resp.json() == []  # revoked scopes aren't "active" scopes anymore


# --- DELETE /subadmins/{id} (demote) -----------------------------------------


async def test_admin_can_demote_a_subadmin(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed_admin_and_resident(db_session)
    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/subadmins/promote",
        json={
            "resident_id": str(seeded["resident"].id),
            "location_ids": [str(seeded["wing_a"].id), str(seeded["wing_b"].id)],
        },
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.delete(f"/api/v1/subadmins/{seeded['resident'].id}", headers=headers)
    assert resp.status_code == 204

    role = (
        await db_session.execute(
            select(UserRole).where(
                UserRole.user_id == seeded["resident"].id, UserRole.role == Role.SUB_ADMIN, UserRole.revoked_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    assert role is None  # revoked

    scopes = (
        await db_session.execute(
            select(SubAdminScope).where(
                SubAdminScope.sub_admin_id == seeded["resident"].id, SubAdminScope.revoked_at.is_(None)
            )
        )
    ).scalars().all()
    assert scopes == []  # every scope revoked too

    # Dual-role — RESIDENT role untouched.
    resident_role = (
        await db_session.execute(
            select(UserRole).where(
                UserRole.user_id == seeded["resident"].id, UserRole.role == Role.RESIDENT, UserRole.revoked_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    assert resident_role is not None


async def test_demote_rejects_resident_who_is_not_a_subadmin(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed_admin_and_resident(db_session)
    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])

    resp = await client.delete(f"/api/v1/subadmins/{seeded['resident'].id}", headers=headers)
    assert resp.status_code == 404


async def test_demote_requires_admin(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed_admin_and_resident(db_session)
    headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])
    await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(seeded["resident"].id), "location_ids": [str(seeded["wing_a"].id)]},
        headers=headers,
    )

    resident_headers = auth_headers(
        seeded["resident"].id, seeded["society"].id, Role.SUB_ADMIN, [Role.RESIDENT, Role.SUB_ADMIN]
    )
    resp = await client.delete(f"/api/v1/subadmins/{seeded['resident'].id}", headers=resident_headers)
    assert resp.status_code == 403


async def test_demote_rejects_subadmin_from_another_society(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed_admin_and_resident(db_session)
    other = await _seed_admin_and_resident(db_session)
    admin_headers = auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])
    other_admin_headers = auth_headers(other["admin"].id, other["society"].id, Role.ADMIN, [Role.ADMIN])

    await client.post(
        "/api/v1/subadmins/promote",
        json={"resident_id": str(seeded["resident"].id), "location_ids": [str(seeded["wing_a"].id)]},
        headers=admin_headers,
    )

    # Other society's Admin can't demote a Sub-admin that isn't theirs.
    resp = await client.delete(f"/api/v1/subadmins/{seeded['resident'].id}", headers=other_admin_headers)
    assert resp.status_code == 404

    # It's still intact from the actual owning Admin's perspective.
    resp = await client.get(f"/api/v1/subadmins/{seeded['resident'].id}/scopes", headers=admin_headers)
    assert len(resp.json()) == 1
