"""Reports endpoints — Admin/Sub-admin/Resident dashboards (v1.5)."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.report import ManagerPerformanceOut, MaintenanceSummaryOut, MyComplaintForRatingOut
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


@router.get("/my-complaint-ratings", response_model=list[MyComplaintForRatingOut])
async def my_complaint_ratings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> list[MyComplaintForRatingOut]:
    return await report_service.my_complaints_for_rating(db, current.society_id, current.user_id)
