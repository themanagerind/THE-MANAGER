"""
Resident notification service — Phase 1 in-app notifications
(user-requested). generate_overdue_notifications is the batch job meant
to be run by scripts/generate_overdue_notifications.py (cron, no in-app
scheduler exists); everything else backs the Resident-facing bell icon.
"""
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MaintenanceDueStatus, NotificationType
from app.models.identity import PropertyResident
from app.models.notifications import ResidentNotification
from app.models.payments import MaintenanceDue


async def generate_overdue_notifications(db: AsyncSession) -> int:
    """For every still-PENDING due whose due_date has passed, notify every
    active resident (Owner and/or Tenant, Section 12) on that property —
    once each, ever, per due. Dedup is a pre-check here (not a try/except
    around each insert) so one due's already-notified residents don't
    trip a rollback that would also undo other residents/dues already
    added earlier in the same run; the DB's own unique constraint
    (ux_resident_notifications_dedup) is still the backstop against a
    concurrent run."""
    today = date.today()
    overdue_dues = (
        await db.execute(
            select(MaintenanceDue).where(
                MaintenanceDue.status == MaintenanceDueStatus.PENDING,
                MaintenanceDue.due_date < today,
            )
        )
    ).scalars().all()

    created = 0
    for due in overdue_dues:
        active_resident_ids = set(
            (
                await db.execute(
                    select(PropertyResident.resident_id).where(
                        PropertyResident.property_id == due.property_id,
                        PropertyResident.is_active.is_(True),
                    )
                )
            ).scalars().all()
        )
        if not active_resident_ids:
            continue

        already_notified = set(
            (
                await db.execute(
                    select(ResidentNotification.resident_id).where(
                        ResidentNotification.related_due_id == due.id,
                        ResidentNotification.type == NotificationType.MAINTENANCE_OVERDUE,
                    )
                )
            ).scalars().all()
        )

        days_overdue = (today - due.due_date).days
        billing_label = due.billing_month.strftime("%B %Y")
        for resident_id in active_resident_ids - already_notified:
            db.add(
                ResidentNotification(
                    society_id=due.society_id,
                    resident_id=resident_id,
                    type=NotificationType.MAINTENANCE_OVERDUE,
                    title="Maintenance overdue",
                    message=(
                        f"Your maintenance of ₹{due.amount} for {billing_label} is "
                        f"{days_overdue} day(s) overdue."
                    ),
                    related_due_id=due.id,
                    created_at=datetime.now(timezone.utc),
                )
            )
            created += 1

    await db.commit()
    return created


async def list_my_notifications(
    db: AsyncSession, resident_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> tuple[list[ResidentNotification], int]:
    total = (
        await db.execute(
            select(func.count()).select_from(ResidentNotification).where(
                ResidentNotification.resident_id == resident_id
            )
        )
    ).scalar_one()
    rows = (
        await db.execute(
            select(ResidentNotification).where(ResidentNotification.resident_id == resident_id)
            .order_by(ResidentNotification.created_at.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()
    return rows, total


async def unread_count(db: AsyncSession, resident_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(ResidentNotification).where(
                ResidentNotification.resident_id == resident_id, ResidentNotification.is_read.is_(False)
            )
        )
    ).scalar_one()


async def mark_read(
    db: AsyncSession, resident_id: uuid.UUID, notification_id: uuid.UUID
) -> ResidentNotification:
    notification = (
        await db.execute(
            select(ResidentNotification).where(
                ResidentNotification.id == notification_id, ResidentNotification.resident_id == resident_id
            )
        )
    ).scalar_one_or_none()
    if notification is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return notification


async def mark_all_read(db: AsyncSession, resident_id: uuid.UUID) -> int:
    result = await db.execute(
        update(ResidentNotification)
        .where(ResidentNotification.resident_id == resident_id, ResidentNotification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.commit()
    return result.rowcount
