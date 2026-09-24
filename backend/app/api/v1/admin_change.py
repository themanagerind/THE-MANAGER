"""Admin change request endpoints — Platform Owner initiates, every
Sub-admin in the society must approve (see app/services/
admin_change_service.py for the full flow)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.admin_change import (
    AdminChangeDecisionIn,
    AdminChangeRequestIn,
    AdminChangeRequestOut,
    PendingAdminChangeApprovalOut,
)
from app.services import admin_change_service

router = APIRouter(prefix="/admin-change-requests", tags=["admin-change"])


@router.post("", response_model=AdminChangeRequestOut)
async def create(
    body: AdminChangeRequestIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> AdminChangeRequestOut:
    row = await admin_change_service.create_admin_change_request(db, body, current.user_id)
    return AdminChangeRequestOut(**row)


@router.get("", response_model=list[AdminChangeRequestOut])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> list[AdminChangeRequestOut]:
    rows = await admin_change_service.list_admin_change_requests(db)
    return [AdminChangeRequestOut(**r) for r in rows]


@router.get("/pending-for-me", response_model=list[PendingAdminChangeApprovalOut])
async def pending_for_me(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.SUB_ADMIN))],
) -> list[PendingAdminChangeApprovalOut]:
    rows = await admin_change_service.list_pending_approvals_for_subadmin(db, current.society_id, current.user_id)
    return [PendingAdminChangeApprovalOut(**r) for r in rows]


@router.post("/{request_id}/decision", response_model=AdminChangeRequestOut)
async def decide(
    request_id: uuid.UUID,
    body: AdminChangeDecisionIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.SUB_ADMIN))],
) -> AdminChangeRequestOut:
    row = await admin_change_service.decide_admin_change_approval(
        db, current.society_id, current.user_id, request_id, body.approve
    )
    return AdminChangeRequestOut(**row)
