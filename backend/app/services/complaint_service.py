"""Complaint service — Section 17."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ComplaintStatus, Role
from app.models.identity import UserRole
from app.models.operations import Complaint, ComplaintAssignment
from app.services.scope_service import resident_owns_or_rents_property, subadmin_has_scope_over_property, user_has_active_role


async def create_complaint(
    db: AsyncSession, society_id: uuid.UUID, resident_id: uuid.UUID, property_id: uuid.UUID,
    category: str, title: str, description: str,
) -> Complaint:
    # CRITICAL fix (audit round-8): a Resident could previously name ANY
    # property in their own society, not just one they're linked to.
    if not await resident_owns_or_rents_property(db, resident_id, property_id, society_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You are not an active Owner/Tenant of this property"
        )

    complaint = Complaint(
        society_id=society_id, property_id=property_id, resident_id=resident_id,
        category=category, title=title, description=description, status=ComplaintStatus.OPEN,
    )
    db.add(complaint)
    await db.commit()
    await db.refresh(complaint)
    return complaint


async def get_complaint(db: AsyncSession, society_id: uuid.UUID, complaint_id: uuid.UUID) -> Complaint:
    complaint = (
        await db.execute(select(Complaint).where(Complaint.id == complaint_id, Complaint.society_id == society_id))
    ).scalar_one_or_none()
    if complaint is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Complaint not found in this society")
    return complaint


async def list_complaints(db: AsyncSession, society_id: uuid.UUID) -> list[Complaint]:
    """Admin: society-wide. Sub-admin scope filtering happens in the router
    (Section 7: Sub-admin only handles complaints within assigned scope)."""
    return (await db.execute(select(Complaint).where(Complaint.society_id == society_id))).scalars().all()


async def list_my_complaints(db: AsyncSession, society_id: uuid.UUID, resident_id: uuid.UUID) -> list[Complaint]:
    return (
        await db.execute(
            select(Complaint).where(Complaint.society_id == society_id, Complaint.resident_id == resident_id)
        )
    ).scalars().all()


async def _assert_subadmin_scope(
    db: AsyncSession, society_id: uuid.UUID, actor_role: Role, actor_id: uuid.UUID, complaint: Complaint
) -> None:
    """CRITICAL fix (audit round-8): PATCH .../status and POST .../assign had
    no Sub-admin scope check at all — a Sub-admin could modify/assign a
    complaint outside their assigned wing/row."""
    if actor_role == Role.SUB_ADMIN and not await subadmin_has_scope_over_property(
        db, actor_id, complaint.property_id, society_id
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Complaint's property is outside your assigned scope")


async def update_status(
    db: AsyncSession, society_id: uuid.UUID, actor_id: uuid.UUID, actor_role: Role,
    complaint_id: uuid.UUID, new_status: ComplaintStatus,
) -> Complaint:
    complaint = await get_complaint(db, society_id, complaint_id)
    await _assert_subadmin_scope(db, society_id, actor_role, actor_id, complaint)
    complaint.status = new_status
    await db.commit()
    await db.refresh(complaint)
    return complaint


async def assign_complaint(
    db: AsyncSession, society_id: uuid.UUID, actor_id: uuid.UUID, actor_role: Role,
    complaint_id: uuid.UUID, assigned_to: uuid.UUID,
) -> ComplaintAssignment:
    complaint = await get_complaint(db, society_id, complaint_id)
    await _assert_subadmin_scope(db, society_id, actor_role, actor_id, complaint)

    if not await user_has_active_role(db, assigned_to, society_id, Role.MANAGER):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "assigned_to must be an active Manager in this society (Section 49.8)",
        )

    # Close out any existing current assignment (append-only pattern,
    # Section 17/49 — DB partial unique index also guarantees this).
    now = datetime.now(timezone.utc)
    current = (
        await db.execute(
            select(ComplaintAssignment).where(
                ComplaintAssignment.complaint_id == complaint_id, ComplaintAssignment.completed_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if current is not None:
        current.completed_at = now

    assignment = ComplaintAssignment(
        complaint_id=complaint_id, assigned_to=assigned_to, assigned_by=actor_id, assigned_at=now
    )
    db.add(assignment)
    complaint.status = ComplaintStatus.IN_PROGRESS
    await db.commit()
    await db.refresh(assignment)
    return assignment


async def filter_by_subadmin_scope(
    db: AsyncSession, society_id: uuid.UUID, complaints: list[Complaint], sub_admin_id: uuid.UUID
) -> list[Complaint]:
    result = []
    for c in complaints:
        if await subadmin_has_scope_over_property(db, sub_admin_id, c.property_id, society_id):
            result.append(c)
    return result
