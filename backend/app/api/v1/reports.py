"""Reports endpoints — Admin/Sub-admin/Resident dashboards (v1.5)."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.report import ComplaintForRatingOut, ManagerPerformanceOut, MaintenanceSummaryOut
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/maintenance-summary", response_model=MaintenanceSummaryOut)
async def maintenance_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.RESIDENT))],
) -> MaintenanceSummaryOut:
    return await report_service.maintenance_summary(db, current.society_id, current.active_role, current.user_id)


@router.get("/manager-performance", response_model=list[ManagerPerformanceOut])
async def manager_performance(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.RESIDENT))],
) -> list[ManagerPerformanceOut]:
    return await report_service.manager_performance(db, current.society_id)


@router.get("/rateable-complaints", response_model=list[ComplaintForRatingOut])
async def rateable_complaints(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT, Role.SUB_ADMIN))],
) -> list[ComplaintForRatingOut]:
    """Resident: their own resolved complaints. Sub-admin: any resolved
    complaint within their assigned Wing/Row scope, plus any they raised
    themselves."""
    return await report_service.complaints_for_rating(db, current.society_id, current.active_role, current.user_id)
