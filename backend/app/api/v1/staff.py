"""Manager/Security Guard staff endpoints — Admin-only. Both roles are
third-party hired staff (no property link, no approval wait) — see
app/services/staff_service.py."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.staff import StaffCreateIn, StaffOut
from app.services import staff_service

router = APIRouter(prefix="/staff", tags=["staff"])


@router.post("", response_model=StaffOut)
async def create_staff(
    body: StaffCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> StaffOut:
    row = await staff_service.create_staff(
        db, current.society_id, body.full_name, body.mobile, body.email, body.role, current.user_id
    )
    return StaffOut(**row)


@router.get("", response_model=list[StaffOut])
async def list_staff(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> list[StaffOut]:
    rows = await staff_service.list_staff(db, current.society_id)
    return [StaffOut(**r) for r in rows]


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_staff(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> None:
    await staff_service.remove_staff(db, current.society_id, user_id)
