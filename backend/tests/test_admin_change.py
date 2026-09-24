"""Admin change requests — Platform Owner-initiated replacement of a
society's Admin, requiring unanimous Sub-admin sign-off. Also covers the
new one-Admin-per-society rule (admin_service.signup_admin's new check +
the DB trigger backing it, migration 0008)."""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, Role, SocietyStatus, UserStatus
from app.models.identity import Property, Society, SocietyLocation, User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed(db_session: AsyncSession, subadmin_count: int = 2) -> dict:
    society = Society(name="Admin Change Test Society", code=f"SOC-ADMCHG-{uuid.uuid4().hex[:6]}", status=SocietyStatus.ACTIVE)
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

    owner = User(society_id=None, full_name="Platform Owner", mobile=f"9{uuid.uuid4().hex[:9]}", status=UserStatus.ACTIVE)
    admin = User(society_id=society.id, full_name="Current Admin", mobile=f"9{uuid.uuid4().hex[:9]}", status=UserStatus.ACTIVE)
    db_session.add_all([owner, admin])
    await db_session.flush()
    db_session.add_all([
        UserRole(user_id=owner.id, role=Role.PLATFORM_OWNER, assigned_at=datetime.now(timezone.utc)),
        UserRole(user_id=admin.id, role=Role.ADMIN, assigned_at=datetime.now(timezone.utc)),
    ])

    subadmins = []
    for i in range(subadmin_count):
        sa = User(society_id=society.id, full_name=f"Sub-admin {i}", mobile=f"9{uuid.uuid4().hex[:9]}", status=UserStatus.ACTIVE)
        db_session.add(sa)
        await db_session.flush()
        db_session.add(UserRole(user_id=sa.id, role=Role.SUB_ADMIN, assigned_at=datetime.now(timezone.utc)))
        subadmins.append(sa)

    await db_session.commit()
    return {"society": society, "prop": prop, "owner": owner, "admin": admin, "subadmins": subadmins}


def _owner_headers(seeded: dict) -> dict:
    return auth_headers(seeded["owner"].id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])


def _subadmin_headers(seeded: dict, i: int = 0) -> dict:
    sa = seeded["subadmins"][i]
    return auth_headers(sa.id, seeded["society"].id, Role.SUB_ADMIN, [Role.SUB_ADMIN])


def _admin_headers(seeded: dict) -> dict:
    return auth_headers(seeded["admin"].id, seeded["society"].id, Role.ADMIN, [Role.ADMIN])


def _body(seeded: dict, mobile: str = "9900000001") -> dict:
    return {
        "society_id": str(seeded["society"].id), "new_admin_full_name": "Incoming Admin",
        "new_admin_mobile": mobile, "new_admin_email": None,
    }


# --- One Admin per society -----------------------------------------------


async def test_admin_signup_rejects_second_admin_for_same_society(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session, subadmin_count=0)
    resp = await client.post(
        "/api/v1/admins/signup",
        json={
            "full_name": "Second Admin", "mobile": "9910000001", "society_id": str(seeded["society"].id),
            "existing_property_id": str(seeded["prop"].id), "existing_property_relationship": "TENANT",
        },
    )
    assert resp.status_code == 409


# --- Create request --------------------------------------------------------


async def test_create_requires_platform_owner(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session)
    resp = await client.post("/api/v1/admin-change-requests", json=_body(seeded), headers=_admin_headers(seeded))
    assert resp.status_code == 403


async def test_create_rejects_society_with_no_admin(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session, subadmin_count=0)
    # Remove the existing Admin's role to simulate "no active Admin".
    role = (
        await db_session.execute(
            select(UserRole).where(UserRole.user_id == seeded["admin"].id, UserRole.role == Role.ADMIN)
        )
    ).scalar_one()
    role.revoked_at = datetime.now(timezone.utc)
    await db_session.commit()

    resp = await client.post("/api/v1/admin-change-requests", json=_body(seeded), headers=_owner_headers(seeded))
    assert resp.status_code == 409


async def test_create_rejects_duplicate_mobile_in_society(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session, subadmin_count=0)
    resp = await client.post(
        "/api/v1/admin-change-requests", json=_body(seeded, mobile=seeded["admin"].mobile),
        headers=_owner_headers(seeded),
    )
    assert resp.status_code == 409


async def test_create_with_no_subadmins_finalizes_immediately(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session, subadmin_count=0)
    resp = await client.post("/api/v1/admin-change-requests", json=_body(seeded), headers=_owner_headers(seeded))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "APPROVED"
    assert body["approvals_total"] == 0
    assert body["new_admin_id"] is not None

    old_role = (
        await db_session.execute(
            select(UserRole).where(UserRole.user_id == seeded["admin"].id, UserRole.role == Role.ADMIN)
        )
    ).scalar_one()
    assert old_role.revoked_at is not None

    new_role = (
        await db_session.execute(
            select(UserRole).where(
                UserRole.user_id == uuid.UUID(body["new_admin_id"]), UserRole.role == Role.ADMIN,
                UserRole.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    assert new_role is not None


async def test_create_with_subadmins_stays_pending(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session, subadmin_count=2)
    resp = await client.post("/api/v1/admin-change-requests", json=_body(seeded), headers=_owner_headers(seeded))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["approvals_total"] == 2
    assert body["approvals_done"] == 0
    assert body["new_admin_id"] is None

    # Old Admin unaffected while pending.
    old_role = (
        await db_session.execute(
            select(UserRole).where(UserRole.user_id == seeded["admin"].id, UserRole.role == Role.ADMIN)
        )
    ).scalar_one()
    assert old_role.revoked_at is None


# --- Decisions --------------------------------------------------------------


async def test_all_subadmins_approve_finalizes(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session, subadmin_count=2)
    resp = await client.post("/api/v1/admin-change-requests", json=_body(seeded), headers=_owner_headers(seeded))
    request_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/admin-change-requests/{request_id}/decision", json={"approve": True},
        headers=_subadmin_headers(seeded, 0),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PENDING"
    assert resp.json()["approvals_done"] == 1

    resp = await client.post(
        f"/api/v1/admin-change-requests/{request_id}/decision", json={"approve": True},
        headers=_subadmin_headers(seeded, 1),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "APPROVED"
    assert body["approvals_done"] == 2
    assert body["new_admin_id"] is not None

    # New Admin can actually log in.
    new_admin_headers = auth_headers(uuid.UUID(body["new_admin_id"]), seeded["society"].id, Role.ADMIN, [Role.ADMIN])
    resp = await client.get("/api/v1/properties", headers=new_admin_headers)
    assert resp.status_code == 200


async def test_single_reject_cancels_whole_request(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session, subadmin_count=2)
    resp = await client.post("/api/v1/admin-change-requests", json=_body(seeded), headers=_owner_headers(seeded))
    request_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/admin-change-requests/{request_id}/decision", json={"approve": True},
        headers=_subadmin_headers(seeded, 0),
    )
    assert resp.status_code == 200

    resp = await client.post(
        f"/api/v1/admin-change-requests/{request_id}/decision", json={"approve": False},
        headers=_subadmin_headers(seeded, 1),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"

    # Old Admin still holds their role — nothing changed.
    old_role = (
        await db_session.execute(
            select(UserRole).where(UserRole.user_id == seeded["admin"].id, UserRole.role == Role.ADMIN)
        )
    ).scalar_one()
    assert old_role.revoked_at is None

    # A rejected request can't be decided again.
    resp = await client.post(
        f"/api/v1/admin-change-requests/{request_id}/decision", json={"approve": True},
        headers=_subadmin_headers(seeded, 0),
    )
    assert resp.status_code == 409


async def test_decide_rejects_someone_not_assigned(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session, subadmin_count=1)
    other = await _seed(db_session, subadmin_count=1)
    resp = await client.post("/api/v1/admin-change-requests", json=_body(seeded), headers=_owner_headers(seeded))
    request_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/admin-change-requests/{request_id}/decision", json={"approve": True},
        headers=_subadmin_headers(other, 0),
    )
    assert resp.status_code == 404


async def test_decide_rejects_double_decision(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session, subadmin_count=2)
    resp = await client.post("/api/v1/admin-change-requests", json=_body(seeded), headers=_owner_headers(seeded))
    request_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/admin-change-requests/{request_id}/decision", json={"approve": True},
        headers=_subadmin_headers(seeded, 0),
    )
    assert resp.status_code == 200

    resp = await client.post(
        f"/api/v1/admin-change-requests/{request_id}/decision", json={"approve": True},
        headers=_subadmin_headers(seeded, 0),
    )
    assert resp.status_code == 409


async def test_pending_for_me_lists_only_assigned_requests(client: AsyncClient, db_session: AsyncSession):
    seeded = await _seed(db_session, subadmin_count=2)
    resp = await client.post("/api/v1/admin-change-requests", json=_body(seeded), headers=_owner_headers(seeded))
    request_id = resp.json()["id"]

    resp = await client.get("/api/v1/admin-change-requests/pending-for-me", headers=_subadmin_headers(seeded, 0))
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["request_id"] == request_id
    assert rows[0]["new_admin_full_name"] == "Incoming Admin"

    # Decide it — no longer pending for that Sub-admin.
    await client.post(
        f"/api/v1/admin-change-requests/{request_id}/decision", json={"approve": True},
        headers=_subadmin_headers(seeded, 0),
    )
    resp = await client.get("/api/v1/admin-change-requests/pending-for-me", headers=_subadmin_headers(seeded, 0))
    assert resp.json() == []

    # Still pending for the OTHER Sub-admin.
    resp = await client.get("/api/v1/admin-change-requests/pending-for-me", headers=_subadmin_headers(seeded, 1))
    assert len(resp.json()) == 1
