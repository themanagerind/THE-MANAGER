"""Reports tests (v1.5): Monthly Maintenance summary and Manager
Performance scorecard, scoped correctly per role."""
from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    ComplaintStatus, HouseType, LocationType, MaintenanceDueStatus, RelationshipType, Role, TodoStatus, UserStatus,
)
from app.models.identity import Property, PropertyResident, SocietyLocation, SubAdminScope, User, UserRole
from app.models.operations import Complaint, ComplaintAssignment, ComplaintRating, ManagerTodo, TaskSuggestion
from app.models.payments import MaintenanceDue
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_property_with_resident(db_session: AsyncSession, society_id, location, house_number):
    prop = Property(
        society_id=society_id, location_id=location.id, house_number=house_number,
        house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
    )
    db_session.add(prop)
    await db_session.flush()

    resident = User(society_id=society_id, full_name=f"Resident {house_number}", mobile=f"961{house_number}0000", status=UserStatus.ACTIVE)
    db_session.add(resident)
    await db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=now))
    db_session.add(
        PropertyResident(
            society_id=society_id, property_id=prop.id, resident_id=resident.id,
            relationship_type=RelationshipType.OWNER, is_active=True, created_at=now,
        )
    )
    await db_session.commit()
    await db_session.refresh(prop)
    await db_session.refresh(resident)
    return prop, resident


async def test_maintenance_summary_scoped_per_role(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    wing_a = SocietyLocation(society_id=society_id, name="Wing A", location_type=LocationType.WING)
    wing_b = SocietyLocation(society_id=society_id, name="Wing B", location_type=LocationType.WING)
    db_session.add_all([wing_a, wing_b])
    await db_session.flush()

    prop_a, resident_a = await _seed_property_with_resident(db_session, society_id, wing_a, "101")
    prop_b, _resident_b = await _seed_property_with_resident(db_session, society_id, wing_b, "201")

    now = datetime.now(timezone.utc)
    last_month = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)
    due_a_paid = MaintenanceDue(
        society_id=society_id, property_id=prop_a.id, amount=1000.0, due_date=date.today(),
        status=MaintenanceDueStatus.PAID, billing_month=date.today().replace(day=1), generated_at=now, updated_at=now,
    )
    due_a_overdue = MaintenanceDue(
        society_id=society_id, property_id=prop_a.id, amount=500.0, due_date=date.today() - timedelta(days=5),
        status=MaintenanceDueStatus.PENDING, billing_month=last_month, generated_at=now, updated_at=now,
    )
    due_b_pending = MaintenanceDue(
        society_id=society_id, property_id=prop_b.id, amount=2000.0, due_date=date.today() + timedelta(days=5),
        status=MaintenanceDueStatus.PENDING, billing_month=date.today().replace(day=1), generated_at=now, updated_at=now,
    )
    db_session.add_all([due_a_paid, due_a_overdue, due_b_pending])
    await db_session.commit()

    # Admin: society-wide across both wings.
    resp = await client.get("/api/v1/reports/maintenance-summary", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_billed"] == 3500.0
    assert body["total_collected"] == 1000.0
    assert body["total_pending"] == 2500.0
    assert body["overdue_count"] == 1

    # Resident A: only their own property's dues (Wing A).
    resident_headers = auth_headers(resident_a.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.get("/api/v1/reports/maintenance-summary", headers=resident_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_billed"] == 1500.0
    assert body["total_collected"] == 1000.0
    assert body["overdue_count"] == 1

    # Sub-admin scoped only to Wing B — must not see Wing A's numbers.
    subadmin = User(society_id=society_id, full_name="Sub Admin", mobile="9610000099", status=UserStatus.ACTIVE)
    db_session.add(subadmin)
    await db_session.flush()
    db_session.add(UserRole(user_id=subadmin.id, role=Role.SUB_ADMIN, assigned_at=now))
    db_session.add(SubAdminScope(society_id=society_id, sub_admin_id=subadmin.id, location_id=wing_b.id, assigned_by=admin_id, assigned_at=now))
    await db_session.commit()
    subadmin_headers = auth_headers(subadmin.id, society_id, Role.SUB_ADMIN, [Role.SUB_ADMIN])

    resp = await client.get("/api/v1/reports/maintenance-summary", headers=subadmin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_billed"] == 2000.0
    assert body["total_pending"] == 2000.0
    assert body["overdue_count"] == 0


async def test_manager_performance_aggregates_tasks_complaints_and_ratings(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    loc = SocietyLocation(society_id=society_id, name="Wing A", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()
    prop, resident = await _seed_property_with_resident(db_session, society_id, loc, "101")

    manager = User(society_id=society_id, full_name="Manager One", mobile="9620000001", status=UserStatus.ACTIVE)
    db_session.add(manager)
    await db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add(UserRole(user_id=manager.id, role=Role.MANAGER, assigned_at=now))

    task = TaskSuggestion(title="Check water tank", created_by=None)
    db_session.add(task)
    await db_session.flush()
    db_session.add_all([
        ManagerTodo(society_id=society_id, manager_id=manager.id, task_suggestion_id=task.id, task_date=date.today(), status=TodoStatus.DONE, assigned_by=admin_id, completed_at=now),
        ManagerTodo(society_id=society_id, manager_id=manager.id, task_suggestion_id=task.id, task_date=date.today(), status=TodoStatus.PENDING, assigned_by=admin_id),
    ])

    complaint = Complaint(
        society_id=society_id, property_id=prop.id, resident_id=resident.id,
        category="Plumbing", title="Leak", description="...", status=ComplaintStatus.RESOLVED,
    )
    db_session.add(complaint)
    await db_session.flush()
    db_session.add(ComplaintAssignment(complaint_id=complaint.id, assigned_to=manager.id, assigned_by=admin_id, assigned_at=now))
    db_session.add(ComplaintRating(society_id=society_id, complaint_id=complaint.id, resident_id=resident.id, manager_id=manager.id, rating=4))
    await db_session.commit()

    resp = await client.get("/api/v1/reports/manager-performance", headers=admin_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["manager_id"] == str(manager.id)
    assert row["tasks_total"] == 2
    assert row["tasks_completed"] == 1
    assert row["complaints_assigned"] == 1
    assert row["complaints_resolved"] == 1
    assert row["average_rating"] == 4.0
    assert row["ratings_count"] == 1


async def test_my_complaint_ratings_shows_manager_and_rating_status(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    loc = SocietyLocation(society_id=society_id, name="Wing A", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()
    prop, resident = await _seed_property_with_resident(db_session, society_id, loc, "101")
    manager = User(society_id=society_id, full_name="Manager One", mobile="9630000001", status=UserStatus.ACTIVE)
    db_session.add(manager)
    await db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add(UserRole(user_id=manager.id, role=Role.MANAGER, assigned_at=now))

    resolved = Complaint(society_id=society_id, property_id=prop.id, resident_id=resident.id, category="A", title="Resolved one", description="...", status=ComplaintStatus.RESOLVED)
    open_one = Complaint(society_id=society_id, property_id=prop.id, resident_id=resident.id, category="B", title="Still open", description="...", status=ComplaintStatus.OPEN)
    db_session.add_all([resolved, open_one])
    await db_session.flush()
    db_session.add(ComplaintAssignment(complaint_id=resolved.id, assigned_to=manager.id, assigned_by=admin_id, assigned_at=now))
    await db_session.commit()

    resident_headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.get("/api/v1/reports/my-complaint-ratings", headers=resident_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["complaint_id"] == str(resolved.id)
    assert body[0]["resolved_manager_name"] == "Manager One"
    assert body[0]["rating"] is None
