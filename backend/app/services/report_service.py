"""Report service — Reports feature (v1.5). Read-only aggregates for the
Admin/Sub-admin/Resident dashboards' Reports section."""
import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ComplaintStatus, MaintenanceDueStatus, Role, TodoStatus, UserStatus
from app.models.identity import PropertyResident, User, UserRole
from app.models.operations import Complaint, ComplaintAssignment, ComplaintRating, ManagerTodo
from app.models.payments import MaintenanceDue
from app.schemas.report import (
    ComplaintForRatingOut,
    ManagerPerformanceOut,
    MaintenanceSummaryOut,
    SocietyPeopleOverviewOut,
)
from app.services.maintenance_service import compute_penalty
from app.services.scope_service import subadmin_has_scope_over_property


async def _resident_property_ids(db: AsyncSession, society_id: uuid.UUID, resident_id: uuid.UUID) -> set[uuid.UUID]:
    rows = (
        await db.execute(
            select(PropertyResident.property_id).where(
                PropertyResident.society_id == society_id,
                PropertyResident.resident_id == resident_id,
                PropertyResident.is_active.is_(True),
            )
        )
    ).scalars().all()
    return set(rows)


def _summarize_dues(dues: list[MaintenanceDue]) -> MaintenanceSummaryOut:
    today = date.today()
    total_billed = sum(float(d.amount) for d in dues)
    total_collected = sum(float(d.amount) for d in dues if d.status == MaintenanceDueStatus.PAID)
    pending_dues = [d for d in dues if d.status == MaintenanceDueStatus.PENDING]
    total_pending = sum(float(d.amount) for d in pending_dues)
    overdue_dues = [d for d in pending_dues if d.due_date < today]
    total_overdue_amount = sum(float(d.amount) + compute_penalty(d, today) for d in overdue_dues)

    return MaintenanceSummaryOut(
        properties_count=len({d.property_id for d in dues}),
        total_billed=round(total_billed, 2),
        total_collected=round(total_collected, 2),
        total_pending=round(total_pending, 2),
        overdue_count=len(overdue_dues),
        total_overdue_amount=round(total_overdue_amount, 2),
        collection_rate_percent=round(total_collected / total_billed * 100, 1) if total_billed else 0.0,
    )


async def maintenance_summary(
    db: AsyncSession, society_id: uuid.UUID, role: Role, user_id: uuid.UUID
) -> MaintenanceSummaryOut:
    """Admin: society-wide. Sub-admin: dues for properties within their
    assigned scope only. Resident: dues for their own linked propert(y/ies)
    only — same per-role scoping already used everywhere else (payments,
    complaints, amenities)."""
    dues = (
        await db.execute(select(MaintenanceDue).where(MaintenanceDue.society_id == society_id))
    ).scalars().all()

    if role == Role.SUB_ADMIN:
        scoped = []
        for due in dues:
            if await subadmin_has_scope_over_property(db, user_id, due.property_id, society_id):
                scoped.append(due)
        dues = scoped
    elif role == Role.RESIDENT:
        property_ids = await _resident_property_ids(db, society_id, user_id)
        dues = [d for d in dues if d.property_id in property_ids]

    return _summarize_dues(dues)


async def platform_maintenance_summary(db: AsyncSession, society_id: uuid.UUID) -> MaintenanceSummaryOut:
    """Platform Owner — full, unscoped view of any one society (picked by
    society_id, not derived from the caller's own — a Platform Owner has
    no society_id of their own). Same numbers an Admin would see for
    their own society."""
    dues = (
        await db.execute(select(MaintenanceDue).where(MaintenanceDue.society_id == society_id))
    ).scalars().all()
    return _summarize_dues(dues)


async def society_people_overview(db: AsyncSession, society_id: uuid.UUID) -> SocietyPeopleOverviewOut:
    """Platform Owner — headcount across every role in one society: the
    Admin's identity (a society has exactly one active Admin, enforced by
    a DB trigger — Section 8), plus counts of active Sub-admins, Managers,
    Security Guards and Residents. One GROUP BY for the counts instead of
    four separate queries."""
    admin_row = (
        await db.execute(
            select(User.full_name, User.mobile)
            .join(UserRole, UserRole.user_id == User.id)
            .where(
                User.society_id == society_id, User.status == UserStatus.ACTIVE,
                UserRole.role == Role.ADMIN, UserRole.revoked_at.is_(None),
            )
        )
    ).first()

    role_counts = dict(
        (
            await db.execute(
                select(UserRole.role, func.count(func.distinct(UserRole.user_id)))
                .join(User, User.id == UserRole.user_id)
                .where(
                    User.society_id == society_id, User.status == UserStatus.ACTIVE,
                    UserRole.revoked_at.is_(None),
                    UserRole.role.in_([Role.SUB_ADMIN, Role.MANAGER, Role.SECURITY_GUARD, Role.RESIDENT]),
                )
                .group_by(UserRole.role)
            )
        ).all()
    )

    return SocietyPeopleOverviewOut(
        admin_name=admin_row[0] if admin_row else None,
        admin_mobile=admin_row[1] if admin_row else None,
        sub_admin_count=role_counts.get(Role.SUB_ADMIN, 0),
        manager_count=role_counts.get(Role.MANAGER, 0),
        security_guard_count=role_counts.get(Role.SECURITY_GUARD, 0),
        resident_count=role_counts.get(Role.RESIDENT, 0),
    )


async def manager_performance(db: AsyncSession, society_id: uuid.UUID) -> list[ManagerPerformanceOut]:
    """Same society-wide view for Admin, Sub-admin and Resident — a
    Manager is society-wide staff (no per-Wing/Row scoping exists for
    them, unlike Sub-admin), so there's no narrower scope to apply."""
    managers = (
        await db.execute(
            select(User.id, User.full_name)
            .join(UserRole, UserRole.user_id == User.id)
            .where(
                User.society_id == society_id, User.status == UserStatus.ACTIVE,
                UserRole.role == Role.MANAGER, UserRole.revoked_at.is_(None),
            )
        )
    ).all()
    if not managers:
        return []

    task_rows = (
        await db.execute(
            select(ManagerTodo.manager_id, ManagerTodo.status, func.count())
            .where(ManagerTodo.society_id == society_id)
            .group_by(ManagerTodo.manager_id, ManagerTodo.status)
        )
    ).all()
    tasks_total: dict[uuid.UUID, int] = {}
    tasks_completed: dict[uuid.UUID, int] = {}
    for manager_id, todo_status, count in task_rows:
        tasks_total[manager_id] = tasks_total.get(manager_id, 0) + count
        if todo_status == TodoStatus.DONE:
            tasks_completed[manager_id] = tasks_completed.get(manager_id, 0) + count

    # Only the CURRENT assignment per complaint (completed_at IS NULL) —
    # the same one complaint_service.rate_complaint attributes a rating
    # to, so "assigned to" and "resolved by" here line up with it.
    complaint_rows = (
        await db.execute(
            select(ComplaintAssignment.assigned_to, Complaint.status, func.count())
            .join(Complaint, Complaint.id == ComplaintAssignment.complaint_id)
            .where(Complaint.society_id == society_id, ComplaintAssignment.completed_at.is_(None))
            .group_by(ComplaintAssignment.assigned_to, Complaint.status)
        )
    ).all()
    complaints_assigned: dict[uuid.UUID, int] = {}
    complaints_resolved: dict[uuid.UUID, int] = {}
    for manager_id, complaint_status, count in complaint_rows:
        complaints_assigned[manager_id] = complaints_assigned.get(manager_id, 0) + count
        if complaint_status in (ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED):
            complaints_resolved[manager_id] = complaints_resolved.get(manager_id, 0) + count

    rating_rows = (
        await db.execute(
            select(ComplaintRating.manager_id, func.avg(ComplaintRating.rating), func.count())
            .where(ComplaintRating.society_id == society_id)
            .group_by(ComplaintRating.manager_id)
        )
    ).all()
    average_rating = {manager_id: float(avg) for manager_id, avg, _count in rating_rows}
    ratings_count = {manager_id: count for manager_id, _avg, count in rating_rows}

    return [
        ManagerPerformanceOut(
            manager_id=manager_id, manager_name=full_name,
            tasks_total=tasks_total.get(manager_id, 0), tasks_completed=tasks_completed.get(manager_id, 0),
            complaints_assigned=complaints_assigned.get(manager_id, 0),
            complaints_resolved=complaints_resolved.get(manager_id, 0),
            average_rating=round(average_rating[manager_id], 2) if manager_id in average_rating else None,
            ratings_count=ratings_count.get(manager_id, 0),
        )
        for manager_id, full_name in managers
    ]


async def complaints_for_rating(
    db: AsyncSession, society_id: uuid.UUID, role: Role, user_id: uuid.UUID
) -> list[ComplaintForRatingOut]:
    """RESOLVED/CLOSED complaints the caller is allowed to rate, with the
    current assignment's Manager and this complaint's rating (if any
    already given) resolved inline — everything the "rate this Manager"
    screen needs in one call. Resident: only their own. Sub-admin: any
    complaint within their assigned Wing/Row scope, plus any they raised
    themselves even outside it (same authorization rule as
    complaint_service.rate_complaint — mirrored here rather than shared,
    since this filters a list instead of gating a single write)."""
    complaints = (
        await db.execute(
            select(Complaint).where(
                Complaint.society_id == society_id,
                Complaint.status.in_([ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED]),
            ).order_by(Complaint.created_at.desc())
        )
    ).scalars().all()

    if role == Role.RESIDENT:
        complaints = [c for c in complaints if c.resident_id == user_id]
    else:  # Role.SUB_ADMIN
        scoped = []
        for c in complaints:
            if c.resident_id == user_id or await subadmin_has_scope_over_property(db, user_id, c.property_id, society_id):
                scoped.append(c)
        complaints = scoped

    if not complaints:
        return []

    complaint_ids = [c.id for c in complaints]
    resident_rows = (
        await db.execute(select(User.id, User.full_name).where(User.id.in_({c.resident_id for c in complaints})))
    ).all()
    resident_name_by_id = dict(resident_rows)

    assignment_rows = (
        await db.execute(
            select(ComplaintAssignment.complaint_id, ComplaintAssignment.assigned_to, User.full_name)
            .join(User, User.id == ComplaintAssignment.assigned_to)
            .where(ComplaintAssignment.complaint_id.in_(complaint_ids), ComplaintAssignment.completed_at.is_(None))
        )
    ).all()
    manager_by_complaint = {row[0]: (row[1], row[2]) for row in assignment_rows}

    rating_rows = (
        await db.execute(
            select(ComplaintRating.complaint_id, ComplaintRating.rating, ComplaintRating.created_at)
            .where(ComplaintRating.complaint_id.in_(complaint_ids))
        )
    ).all()
    rating_by_complaint = {row[0]: (row[1], row[2]) for row in rating_rows}

    result = []
    for c in complaints:
        manager_id, manager_name = manager_by_complaint.get(c.id, (None, None))
        rating, rated_at = rating_by_complaint.get(c.id, (None, None))
        result.append(
            ComplaintForRatingOut(
                complaint_id=c.id, title=c.title, category=c.category, status=c.status, created_at=c.created_at,
                resident_id=c.resident_id, resident_name=resident_name_by_id.get(c.resident_id, "—"),
                resolved_manager_id=manager_id, resolved_manager_name=manager_name,
                rating=rating, rated_at=rated_at,
            )
        )
    return result
