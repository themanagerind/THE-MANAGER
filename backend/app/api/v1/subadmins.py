"""Sub-admin endpoints — promotion, scope management, resignation flow."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.subadmin import (
    AssignScopeIn,
    PromoteToSubAdminIn,
    ResignationDecisionIn,
    ResignationRequestIn,
    RoleRequestOut,
    SubAdminAssignmentOut,
    SubAdminScopeOut,
)
from app.services import subadmin_service

router = APIRouter(prefix="/subadmins", tags=["subadmins"])


@router.get("", response_model=list[SubAdminAssignmentOut])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> list[SubAdminAssignmentOut]:
    """Every active Sub-admin scope in the society — the Assign Sub-admin
    page's "Current Sub-admins" overview."""
    rows = await subadmin_service.list_all_assignments(db, current.society_id)
    return [SubAdminAssignmentOut(**r) for r in rows]


@router.post("/promote", response_model=list[SubAdminScopeOut])
async def promote(
    body: PromoteToSubAdminIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> list[SubAdminScopeOut]:
    scopes = await subadmin_service.promote_to_subadmin(
        db, current.society_id, body.resident_id, body.location_ids, current.user_id
    )
    return [SubAdminScopeOut.model_validate(s) for s in scopes]


@router.delete("/{sub_admin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def demote(
    sub_admin_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> None:
    """Admin directly removes someone's Sub-admin role and every active
    scope, in one shot — no resignation request needed (that flow is the
    Sub-admin's own choice to step down; this is the Admin's own choice to
    remove them, since promotion is unilateral too)."""
    await subadmin_service.demote_subadmin(db, current.society_id, sub_admin_id)


@router.post("/{sub_admin_id}/scopes", response_model=SubAdminScopeOut)
async def assign_scope(
    sub_admin_id: uuid.UUID,
    body: AssignScopeIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> SubAdminScopeOut:
    scope = await subadmin_service.assign_additional_scope(
        db, current.society_id, sub_admin_id, body.location_id, current.user_id
    )
    return SubAdminScopeOut.model_validate(scope)


@router.delete("/scopes/{scope_id}", response_model=SubAdminScopeOut)
async def revoke_scope(
    scope_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> SubAdminScopeOut:
    scope = await subadmin_service.revoke_scope(db, current.society_id, scope_id)
    return SubAdminScopeOut.model_validate(scope)


@router.get("/{sub_admin_id}/scopes", response_model=list[SubAdminScopeOut])
async def list_scopes(
    sub_admin_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN))],
) -> list[SubAdminScopeOut]:
    # HIGH fix (audit round-8): a Sub-admin could previously pass any other
    # Sub-admin's ID and read their scope assignments (IDOR).
    if current.active_role == Role.SUB_ADMIN and sub_admin_id != current.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sub-admins can only view their own scopes")
    scopes = await subadmin_service.list_subadmin_scopes(db, current.society_id, sub_admin_id)
    return [SubAdminScopeOut.model_validate(s) for s in scopes]


@router.post("/resignation", response_model=RoleRequestOut)
async def submit_resignation(
    body: ResignationRequestIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.SUB_ADMIN))],
) -> RoleRequestOut:
    """Sub-admin submits their own resignation (Section 7/26)."""
    req = await subadmin_service.submit_resignation(db, current.society_id, current.user_id, body.reason)
    return RoleRequestOut.model_validate(req)


@router.get("/resignations/pending", response_model=list[RoleRequestOut])
async def list_pending_resignations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> list[RoleRequestOut]:
    reqs = await subadmin_service.list_pending_resignations(db, current.society_id)
    return [RoleRequestOut.model_validate(r) for r in reqs]


@router.post("/resignations/{request_id}/decision", response_model=RoleRequestOut)
async def decide_resignation(
    request_id: uuid.UUID,
    body: ResignationDecisionIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> RoleRequestOut:
    req = await subadmin_service.decide_resignation(
        db, current.society_id, request_id, body.approve, body.decision_reason, current.user_id
    )
    return RoleRequestOut.model_validate(req)
