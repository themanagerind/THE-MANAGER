"""Notices endpoints — Section 19."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.notice import NoticeCreateIn, NoticeOut
from app.schemas.pagination import Page, Pagination, pagination_params
from app.services import notice_service

router = APIRouter(prefix="/notices", tags=["notices"])


@router.post("", response_model=NoticeOut)
async def create(
    body: NoticeCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> NoticeOut:
    notice = await notice_service.create_notice(db, current.society_id, current.user_id, body.title, body.content)
    return NoticeOut.model_validate(notice)


@router.get("", response_model=Page[NoticeOut])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[
        CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.MANAGER, Role.RESIDENT))
    ],
    pagination: Annotated[Pagination, Depends(pagination_params)],
) -> Page[NoticeOut]:
    # Security Guard excluded — Section 10: Guard only gets visitor/security
    # functionality, notices are outside that scope.
    notices, total = await notice_service.list_notices(db, current.society_id, pagination.skip, pagination.limit)
    return Page(items=[NoticeOut.model_validate(n) for n in notices], total=total, skip=pagination.skip, limit=pagination.limit)
