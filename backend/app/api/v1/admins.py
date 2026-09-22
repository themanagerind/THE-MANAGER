"""Admin self-signup (for an existing society) + Platform Owner approval."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.admin import AdminApprovalIn, AdminOut, AdminSignupIn
from app.services import admin_service

router = APIRouter(prefix="/admins", tags=["admins"])


@router.post("/signup", response_model=AdminOut)
async def signup(
    body: AdminSignupIn, db: Annotated[AsyncSession, Depends(get_db)]
) -> AdminOut:
    """Public — no auth required. Admin waits for Platform Owner approval."""
    admin = await admin_service.signup_admin(db, body)
    return AdminOut.model_validate(admin)


@router.get("/pending", response_model=list[AdminOut])
async def list_pending(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> list[AdminOut]:
    admins = await admin_service.list_pending_admins(db)
    return [AdminOut.model_validate(a) for a in admins]


@router.post("/{admin_id}/approval", response_model=AdminOut)
async def decide_approval(
    admin_id: uuid.UUID,
    body: AdminApprovalIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> AdminOut:
    admin = await admin_service.decide_admin_approval(db, admin_id, body.approve, current.user_id)
    return AdminOut.model_validate(admin)
