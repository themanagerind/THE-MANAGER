"""Complaints endpoints — Section 17."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.complaint import (
    ComplaintAssignIn,
    ComplaintAssignmentOut,
    ComplaintCreateIn,
    ComplaintOut,
    ComplaintRatingIn,
    ComplaintRatingOut,
    ComplaintStatusUpdateIn,
)
from app.services import complaint_service

router = APIRouter(prefix="/complaints", tags=["complaints"])


@router.post("", response_model=ComplaintOut)
async def create(
    body: ComplaintCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> ComplaintOut:
    complaint = await complaint_service.create_complaint(
        db, current.society_id, current.user_id, body.property_id, body.category, body.title, body.description
    )
    return ComplaintOut.model_validate(complaint)


@router.get("", response_model=list[ComplaintOut])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[
        CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.MANAGER, Role.RESIDENT))
    ],
) -> list[ComplaintOut]:
    if current.active_role == Role.RESIDENT:
        complaints = await complaint_service.list_my_complaints(db, current.society_id, current.user_id)
    elif current.active_role == Role.SUB_ADMIN:
        all_complaints = await complaint_service.list_complaints(db, current.society_id)
        complaints = await complaint_service.filter_by_subadmin_scope(
            db, current.society_id, all_complaints, current.user_id
        )
    else:
        complaints = await complaint_service.list_complaints(db, current.society_id)
    return [ComplaintOut.model_validate(c) for c in complaints]


@router.patch("/{complaint_id}/status", response_model=ComplaintOut)
async def update_status(
    complaint_id: uuid.UUID,
    body: ComplaintStatusUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.MANAGER))],
) -> ComplaintOut:
    complaint = await complaint_service.update_status(
        db, current.society_id, current.user_id, current.active_role, complaint_id, body.status
    )
    return ComplaintOut.model_validate(complaint)


@router.post("/{complaint_id}/assign", response_model=ComplaintAssignmentOut)
async def assign(
    complaint_id: uuid.UUID,
    body: ComplaintAssignIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.MANAGER))],
) -> ComplaintAssignmentOut:
    """Assignment target must hold Manager role (Section 49.8); Sub-admin
    caller must have scope over the complaint's property."""
    assignment = await complaint_service.assign_complaint(
        db, current.society_id, current.user_id, current.active_role, complaint_id, body.assigned_to
    )
    return ComplaintAssignmentOut.model_validate(assignment)


@router.post("/{complaint_id}/rating", response_model=ComplaintRatingOut)
async def rate(
    complaint_id: uuid.UUID,
    body: ComplaintRatingIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> ComplaintRatingOut:
    """Only the Resident who raised this complaint can rate the Manager
    who resolved it, once, after it's actually RESOLVED/CLOSED."""
    rating = await complaint_service.rate_complaint(
        db, current.society_id, current.user_id, complaint_id, body.rating
    )
    return ComplaintRatingOut.model_validate(rating)
