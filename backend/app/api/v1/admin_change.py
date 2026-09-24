"""Admin change request endpoints — two ways an Admin gets replaced
(Platform Owner-initiated, or the Admin's own resignation), every
Sub-admin in the society must approve either way (see app/services/
admin_change_service.py for the full flow)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.admin_change import (
    AdminChangeDecisionIn,
    AdminChangeRequestIn,
    AdminChangeRequestOut,
    AdminResignationIn,
    PendingAdminChangeApprovalOut,
    ResignationCandidateOut,
    RoleHistoryOut,
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


@router.get("/resignation-candidates", response_model=list[ResignationCandidateOut])
async def resignation_candidates(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> list[ResignationCandidateOut]:
    rows = await admin_change_service.list_resignation_candidates(db, current.society_id, current.user_id)
    return [ResignationCandidateOut(**r) for r in rows]


@router.post("/resign", response_model=AdminChangeRequestOut)
async def resign(
    body: AdminResignationIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> AdminChangeRequestOut:
    """The Admin resigns and picks their own successor — an existing
    Resident/Sub-admin in their society."""
    row = await admin_change_service.create_resignation_request(
        db, current.society_id, current.user_id, body.new_admin_user_id
    )
    return AdminChangeRequestOut(**row)


@router.get("/history", response_model=list[RoleHistoryOut])
async def history(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.PLATFORM_OWNER))],
    society_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[RoleHistoryOut]:
    """Every ADMIN/SUB_ADMIN this society has ever had, with when they
    started and ended — Admin/Sub-admin see their own society; Platform
    Owner must pass ?society_id= (they don't have one of their own)."""
    target_society_id = society_id if current.active_role == Role.PLATFORM_OWNER else current.society_id
    if target_society_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "society_id is required")
    rows = await admin_change_service.list_role_history(db, target_society_id)
    return [RoleHistoryOut(**r) for r in rows]


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
