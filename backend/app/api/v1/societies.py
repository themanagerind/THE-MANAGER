"""Societies endpoints — public signup + Platform Owner administration."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.society import (
    SocietyCreateIn,
    SocietyLookupOut,
    SocietyOut,
    SocietySignupIn,
    SocietySignupOut,
    SocietyStatusUpdateIn,
)
from app.services import society_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/societies", tags=["societies"])


@router.get("/lookup/{code}", response_model=SocietyLookupOut)
async def lookup(code: str, db: Annotated[AsyncSession, Depends(get_db)]) -> SocietyLookupOut:
    """Public — used by the Admin/Resident signup forms to find their
    society by its code without needing its internal UUID, and without
    exposing the full society list."""
    society = await society_service.lookup_society_by_code(db, code)
    if society is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Society not found")
    return SocietyLookupOut(id=society.id, name=society.name)


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


@router.post("", response_model=SocietyOut)
async def create(
    body: SocietyCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> SocietyOut:
    """A society now only comes into existence this way — created directly
    by the Platform Owner from their dashboard, ACTIVE immediately. Admin
    signup (POST /admins/signup) targets an existing society created here;
    it no longer creates one itself."""
    society = await society_service.create_society(db, body)
    return SocietyOut.model_validate(society)


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
