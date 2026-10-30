"""Resident notification endpoints — Phase 1 in-app notifications
(user-requested)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.notification import ResidentNotificationOut, UnreadCountOut
from app.schemas.pagination import Page, Pagination, pagination_params
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/mine", response_model=Page[ResidentNotificationOut])
async def list_mine(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
    pagination: Annotated[Pagination, Depends(pagination_params)],
) -> Page[ResidentNotificationOut]:
    notifications, total = await notification_service.list_my_notifications(
        db, current.user_id, pagination.skip, pagination.limit
    )
    return Page(
        items=[ResidentNotificationOut.model_validate(n) for n in notifications],
        total=total, skip=pagination.skip, limit=pagination.limit,
    )


@router.get("/unread-count", response_model=UnreadCountOut)
async def unread_count(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> UnreadCountOut:
    count = await notification_service.unread_count(db, current.user_id)
    return UnreadCountOut(count=count)


@router.patch("/{notification_id}/read", response_model=ResidentNotificationOut)
async def mark_read(
    notification_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> ResidentNotificationOut:
    notification = await notification_service.mark_read(db, current.user_id, notification_id)
    return ResidentNotificationOut.model_validate(notification)


@router.post("/mark-all-read", response_model=UnreadCountOut)
async def mark_all_read(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> UnreadCountOut:
    await notification_service.mark_all_read(db, current.user_id)
    return UnreadCountOut(count=await notification_service.unread_count(db, current.user_id))
