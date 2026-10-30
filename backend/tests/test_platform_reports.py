"""Platform Owner's per-society report drill-down (v1.8): pick any one
society by id (no society_id of their own to derive from) and see its
people headcount, Monthly Maintenance summary, Manager performance, and
Income/Expense balance."""
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounts import AccountEntry, AccountHeading
from app.models.enums import (
    EntrySource, EntryType, HouseType, LocationType, MaintenanceDueStatus, Role, UserStatus,
)
from app.models.identity import Property, SocietyLocation, SubAdminScope, User, UserRole
from app.models.payments import MaintenanceDue
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


async def _seed_person(db_session: AsyncSession, society_id, role: Role, mobile: str, name: str) -> User:
    user = User(society_id=society_id, full_name=name, mobile=mobile, status=UserStatus.ACTIVE)
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserRole(user_id=user.id, role=role, assigned_at=datetime.now(timezone.utc)))
    return user


async def test_society_people_overview_counts_every_role(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    owner = await _seed_platform_owner(db_session, "9701000010")
    owner_headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    await _seed_person(db_session, society_id, Role.MANAGER, "9700000011", "Manager One")
    await _seed_person(db_session, society_id, Role.MANAGER, "9700000012", "Manager Two")
    await _seed_person(db_session, society_id, Role.SECURITY_GUARD, "9700000013", "Guard One")
    await _seed_person(db_session, society_id, Role.RESIDENT, "9700000014", "Resident One")
    await _seed_person(db_session, society_id, Role.RESIDENT, "9700000015", "Resident Two")
    await _seed_person(db_session, society_id, Role.RESIDENT, "9700000016", "Resident Three")

    subadmin = await _seed_person(db_session, society_id, Role.SUB_ADMIN, "9700000017", "Sub Admin One")
    await db_session.flush()
    loc = SocietyLocation(society_id=society_id, name="Wing A", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()
    db_session.add(SubAdminScope(society_id=society_id, sub_admin_id=subadmin.id, location_id=loc.id, assigned_by=admin_id, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()

    resp = await client.get(f"/api/v1/reports/platform/{society_id}/overview", headers=owner_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["sub_admin_count"] == 1
    assert body["manager_count"] == 2
    assert body["security_guard_count"] == 1
    assert body["resident_count"] == 3
    assert body["admin_name"] is not None


async def test_platform_maintenance_summary_and_balance_for_a_society(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    owner = await _seed_platform_owner(db_session, "9701000020")
    owner_headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    loc = SocietyLocation(society_id=society_id, name="Wing A", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()
    prop = Property(society_id=society_id, location_id=loc.id, house_number="101", house_type=HouseType.FLAT, floor_number=1, status="ACTIVE")
    db_session.add(prop)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    due = MaintenanceDue(
        society_id=society_id, property_id=prop.id, amount=1200.0, due_date=date.today(),
        status=MaintenanceDueStatus.PAID, billing_month=date.today().replace(day=1), generated_at=now, updated_at=now,
    )
    db_session.add(due)

    heading = AccountHeading(entry_type=EntryType.INCOME, title="Society Maintenance Charges (platform test)")
    db_session.add(heading)
    await db_session.flush()
    entry = AccountEntry(
        society_id=society_id, entry_type=EntryType.INCOME, source=EntrySource.MANUAL, heading_id=heading.id,
        title=heading.title, amount=1200.0, entry_date=date.today(), created_by=admin_id,
    )
    db_session.add(entry)
    await db_session.commit()

    resp = await client.get(f"/api/v1/reports/platform/{society_id}/maintenance-summary", headers=owner_headers)
    assert resp.status_code == 200
    assert resp.json()["total_collected"] == 1200.0

    resp = await client.get(f"/api/v1/reports/platform/{society_id}/balance", headers=owner_headers)
    assert resp.status_code == 200
    assert resp.json()["total_income"] == 1200.0


async def test_platform_manager_performance_for_a_society(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9701000030")
    owner_headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])
    manager = await _seed_person(db_session, society_id, Role.MANAGER, "9700000031", "Manager One")
    await db_session.commit()

    resp = await client.get(f"/api/v1/reports/platform/{society_id}/manager-performance", headers=owner_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["manager_id"] == str(manager.id)
    assert body[0]["tasks_total"] == 0


async def test_platform_reports_isolated_between_societies(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_a = two_societies_with_admins["a"]["society_id"]
    society_b = two_societies_with_admins["b"]["society_id"]
    owner = await _seed_platform_owner(db_session, "9701000040")
    owner_headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])

    await _seed_person(db_session, society_a, Role.MANAGER, "9700000041", "Manager A")
    await db_session.commit()

    resp = await client.get(f"/api/v1/reports/platform/{society_b}/overview", headers=owner_headers)
    assert resp.status_code == 200
    assert resp.json()["manager_count"] == 0


async def test_non_platform_owner_cannot_access_platform_reports(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.get(f"/api/v1/reports/platform/{society_id}/overview", headers=admin_headers)
    assert resp.status_code == 403
