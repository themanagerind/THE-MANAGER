"""Visitors endpoints — Section 18/21 (Guard data boundary)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role, VisitorStatus
from app.schemas.pagination import Page, Pagination, pagination_params
from app.schemas.visitor import GuardVisitorOut, VisitorOut, VisitorPreApproveIn
from app.services import visitor_service
from app.services.scope_service import subadmin_has_scope_over_property

router = APIRouter(prefix="/visitors", tags=["visitors"])


@router.get("", response_model=Page[VisitorOut])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN))],
    pagination: Annotated[Pagination, Depends(pagination_params)],
) -> Page[VisitorOut]:
    """Admin/Sub-admin view of every visitor in the society — was missing
    entirely; only Resident's-own and Guard's restricted projection
    existed before this."""
    if current.active_role == Role.SUB_ADMIN:
        all_visitors = await visitor_service.list_all_visitors_for_society(db, current.society_id)
        scoped = [
            v for v in all_visitors
            if await subadmin_has_scope_over_property(db, current.user_id, v.property_id, current.society_id)
        ]
        total = len(scoped)
        visitors = scoped[pagination.skip : pagination.skip + pagination.limit]
    else:
        visitors, total = await visitor_service.list_visitors_for_society(
            db, current.society_id, pagination.skip, pagination.limit
        )
    return Page(items=[VisitorOut.model_validate(v) for v in visitors], total=total, skip=pagination.skip, limit=pagination.limit)


@router.post("", response_model=VisitorOut)
async def pre_approve(
    body: VisitorPreApproveIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> VisitorOut:
    visitor = await visitor_service.pre_approve(
        db, current.society_id, current.user_id, body.property_id, body.visitor_name,
        body.visitor_mobile, body.visit_date, body.purpose,
    )
    return VisitorOut.model_validate(visitor)


@router.get("/mine", response_model=Page[VisitorOut])
async def my_visitors(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
    pagination: Annotated[Pagination, Depends(pagination_params)],
) -> Page[VisitorOut]:
    visitors, total = await visitor_service.list_visitors_for_resident(
        db, current.society_id, current.user_id, pagination.skip, pagination.limit
    )
    return Page(items=[VisitorOut.model_validate(v) for v in visitors], total=total, skip=pagination.skip, limit=pagination.limit)


@router.patch("/{visitor_id}/status", response_model=VisitorOut)
async def resident_update_status(
    visitor_id: uuid.UUID,
    new_status: VisitorStatus,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> VisitorOut:
    visitor = await visitor_service.resident_update_status(
        db, current.society_id, current.user_id, visitor_id, new_status
    )
    return VisitorOut.model_validate(visitor)


@router.get("/guard-view", response_model=list[GuardVisitorOut])
async def guard_view(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.SECURITY_GUARD))],
) -> list[GuardVisitorOut]:
    """Restricted projection only — Section 21 (no financial/resident data)."""
    rows = await visitor_service.list_visitors_for_guard(db, current.society_id)
    return [
        GuardVisitorOut(
            id=v.id, property_house_number=house_number, visitor_name=v.visitor_name,
            visitor_mobile=v.visitor_mobile, visit_date=v.visit_date, status=v.status,
        )
        for v, house_number in rows
    ]


@router.post("/{visitor_id}/entry", response_model=GuardVisitorOut)
async def guard_mark_entry(
    visitor_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.SECURITY_GUARD))],
) -> GuardVisitorOut:
    visitor = await visitor_service.guard_mark_entry(db, current.society_id, visitor_id, current.user_id)
    return GuardVisitorOut(
        id=visitor.id, property_house_number="", visitor_name=visitor.visitor_name,
        visitor_mobile=visitor.visitor_mobile, visit_date=visitor.visit_date, status=visitor.status,
    )


@router.post("/{visitor_id}/exit", response_model=GuardVisitorOut)
async def guard_mark_exit(
    visitor_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.SECURITY_GUARD))],
) -> GuardVisitorOut:
    visitor = await visitor_service.guard_mark_exit(db, current.society_id, visitor_id, current.user_id)
    return GuardVisitorOut(
        id=visitor.id, property_house_number="", visitor_name=visitor.visitor_name,
        visitor_mobile=visitor.visitor_mobile, visit_date=visitor.visit_date, status=visitor.status,
    )
