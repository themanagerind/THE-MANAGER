"""Resident notification bell — Phase 1 in-app notifications (user-
requested). generate_overdue_notifications is the cron-script batch job
(scripts/generate_overdue_notifications.py); the rest backs the
Resident-facing GET/PATCH endpoints."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    HouseType, LocationType, MaintenanceDueStatus, RelationshipType, Role, UserStatus,
)
from app.models.identity import Property, PropertyResident, SocietyLocation, User, UserRole
from app.models.notifications import ResidentNotification
from app.models.payments import MaintenanceDue
from app.services import notification_service
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_property(db_session: AsyncSession, society_id, house_number="A-1") -> Property:
    loc = SocietyLocation(society_id=society_id, name=f"Wing {uuid.uuid4().hex[:6]}", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()
    prop = Property(
        society_id=society_id, location_id=loc.id, house_number=house_number,
        house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
    )
    db_session.add(prop)
    await db_session.commit()
    await db_session.refresh(prop)
    return prop


async def _seed_resident(
    db_session: AsyncSession, society_id, property_id, mobile: str,
    relationship_type: RelationshipType = RelationshipType.OWNER,
) -> User:
    resident = User(society_id=society_id, full_name="Resident", mobile=mobile, status=UserStatus.ACTIVE)
    db_session.add(resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    db_session.add(
        PropertyResident(
            society_id=society_id, property_id=property_id, resident_id=resident.id,
            relationship_type=relationship_type, is_active=True, start_date=date.today(),
            created_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()
    await db_session.refresh(resident)
    return resident


async def _seed_due(
    db_session: AsyncSession, society_id, property_id, due_date, status=MaintenanceDueStatus.PENDING, amount=2500.0,
    billing_month=None,
) -> MaintenanceDue:
    now = datetime.now(timezone.utc)
    due = MaintenanceDue(
        society_id=society_id, property_id=property_id, amount=amount, due_date=due_date,
        status=status, billing_month=billing_month or date.today().replace(day=1), generated_at=now, updated_at=now,
    )
    db_session.add(due)
    await db_session.commit()
    await db_session.refresh(due)
    return due


async def test_generate_notifies_every_active_resident_on_overdue_property(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    prop = await _seed_property(db_session, society_id)
    owner = await _seed_resident(db_session, society_id, prop.id, "9840000001", RelationshipType.OWNER)
    tenant = await _seed_resident(db_session, society_id, prop.id, "9840000002", RelationshipType.TENANT)
    due = await _seed_due(db_session, society_id, prop.id, due_date=date.today() - timedelta(days=5))

    # >= not == : other test files in the same session-scoped DB (no
    # per-test rollback here) may leave their own overdue dues behind,
    # which this global cron-style scan legitimately also notifies.
    created = await notification_service.generate_overdue_notifications(db_session)
    assert created >= 2

    rows = (
        await db_session.execute(select(ResidentNotification).where(ResidentNotification.related_due_id == due.id))
    ).scalars().all()
    resident_ids = {r.resident_id for r in rows}
    assert resident_ids == {owner.id, tenant.id}
    assert all(r.type.value == "MAINTENANCE_OVERDUE" and not r.is_read for r in rows)


async def test_generate_skips_dues_not_yet_overdue_and_already_paid_dues(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    prop = await _seed_property(db_session, society_id)
    await _seed_resident(db_session, society_id, prop.id, "9840000003")
    not_yet_due = await _seed_due(
        db_session, society_id, prop.id, due_date=date.today() + timedelta(days=5),  # not due yet
        billing_month=date.today().replace(day=1),
    )
    already_paid = await _seed_due(
        db_session, society_id, prop.id, due_date=date.today() - timedelta(days=5),
        status=MaintenanceDueStatus.PAID,
        billing_month=(date.today().replace(day=1) - timedelta(days=1)).replace(day=1),
    )

    await notification_service.generate_overdue_notifications(db_session)

    rows = (
        await db_session.execute(
            select(ResidentNotification).where(
                ResidentNotification.related_due_id.in_([not_yet_due.id, already_paid.id])
            )
        )
    ).scalars().all()
    assert rows == []


async def test_generate_is_idempotent_across_runs(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Running the cron script twice on the same day must not double-
    notify — the dedup pre-check (resident_id, related_due_id, type)."""
    society_id = two_societies_with_admins["a"]["society_id"]
    prop = await _seed_property(db_session, society_id)
    resident = await _seed_resident(db_session, society_id, prop.id, "9840000004")
    due = await _seed_due(db_session, society_id, prop.id, due_date=date.today() - timedelta(days=3))

    # Counts aren't asserted directly (>= elsewhere) — other test files'
    # leftover overdue dues in this session-scoped DB would inflate them.
    # What actually matters: the second run adds nothing NEW for this
    # specific resident+due, checked via the exact-count query below.
    await notification_service.generate_overdue_notifications(db_session)
    await notification_service.generate_overdue_notifications(db_session)

    matching = (
        await db_session.execute(
            select(ResidentNotification).where(
                ResidentNotification.resident_id == resident.id, ResidentNotification.related_due_id == due.id
            )
        )
    ).scalars().all()
    assert len(matching) == 1


async def test_resident_can_list_and_mark_read(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    prop = await _seed_property(db_session, society_id)
    resident = await _seed_resident(db_session, society_id, prop.id, "9840000005")
    await _seed_due(db_session, society_id, prop.id, due_date=date.today() - timedelta(days=2))
    await notification_service.generate_overdue_notifications(db_session)

    headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.get("/api/v1/notifications/unread-count", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["count"] == 1

    resp = await client.get("/api/v1/notifications/mine", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    notification_id = items[0]["id"]
    assert items[0]["is_read"] is False

    resp = await client.patch(f"/api/v1/notifications/{notification_id}/read", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True

    resp = await client.get("/api/v1/notifications/unread-count", headers=headers)
    assert resp.json()["count"] == 0


async def test_mark_all_read(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    society_id = two_societies_with_admins["a"]["society_id"]
    prop = await _seed_property(db_session, society_id)
    resident = await _seed_resident(db_session, society_id, prop.id, "9840000006")
    await _seed_due(
        db_session, society_id, prop.id, due_date=date.today() - timedelta(days=1),
        billing_month=date.today().replace(day=1),
    )
    await _seed_due(
        db_session, society_id, prop.id, due_date=date.today() - timedelta(days=10), amount=500.0,
        billing_month=(date.today().replace(day=1) - timedelta(days=1)).replace(day=1),
    )
    await notification_service.generate_overdue_notifications(db_session)

    headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.get("/api/v1/notifications/unread-count", headers=headers)
    assert resp.json()["count"] == 2

    resp = await client.post("/api/v1/notifications/mark-all-read", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


async def test_resident_cannot_mark_another_residents_notification_read(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    prop = await _seed_property(db_session, society_id)
    resident = await _seed_resident(db_session, society_id, prop.id, "9840000007")
    other_prop = await _seed_property(db_session, society_id, "A-2")
    other = await _seed_resident(db_session, society_id, other_prop.id, "9840000008")
    await _seed_due(db_session, society_id, prop.id, due_date=date.today() - timedelta(days=1))
    await notification_service.generate_overdue_notifications(db_session)

    notification = (
        await db_session.execute(select(ResidentNotification).where(ResidentNotification.resident_id == resident.id))
    ).scalar_one()

    other_headers = auth_headers(other.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.patch(f"/api/v1/notifications/{notification.id}/read", headers=other_headers)
    assert resp.status_code == 404


async def test_non_resident_cannot_access_notifications(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    admin_id = two_societies_with_admins["a"]["admin_id"]
    society_id = two_societies_with_admins["a"]["society_id"]
    headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.get("/api/v1/notifications/mine", headers=headers)
    assert resp.status_code == 403
