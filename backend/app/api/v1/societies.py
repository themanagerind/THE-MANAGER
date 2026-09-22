"""Societies endpoints — public signup + Platform Owner administration."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.society import (
    SocietyOut,
    SocietySignupIn,
    SocietySignupOut,
    SocietyStatusUpdateIn,
)
from app.services import society_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/societies", tags=["societies"])


@router.post("/signup", response_model=SocietySignupOut)
async def signup(
    body: SocietySignupIn, db: Annotated[AsyncSession, Depends(get_db)]
) -> SocietySignupOut:
    """Public — no auth required. Creates a PENDING society + PENDING Admin
    together; both wait for Platform Owner approval (Section 26)."""
    society, admin = await society_service.signup_society_and_admin(db, body)
    return SocietySignupOut(society_id=society.id, admin_user_id=admin.id)


@router.get("", response_model=list[SocietyOut])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> list[SocietyOut]:
    societies = await society_service.list_societies(db)
    return [SocietyOut.model_validate(s) for s in societies]


@router.post("/{society_id}/approve", response_model=SocietyOut)
async def approve(
    society_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> SocietyOut:
    society = await society_service.approve_society_and_admin(db, society_id, current.user_id)
    return SocietyOut.model_validate(society)


@router.patch("/{society_id}/status", response_model=SocietyOut)
async def update_status(
    society_id: uuid.UUID,
    body: SocietyStatusUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> SocietyOut:
    society = await society_service.update_society_status(db, society_id, body.status)
    return SocietyOut.model_validate(society)
