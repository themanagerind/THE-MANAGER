"""Reports endpoints — Admin/Sub-admin/Resident dashboards (v1.5),
plus Platform Owner's per-society drill-down (v1.8)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.account_entry import BalanceSummaryOut
from app.schemas.report import (
    ComplaintForRatingOut,
    ManagerPerformanceOut,
    MaintenanceSummaryOut,
    SocietyPeopleOverviewOut,
)
from app.services import account_entry_service, report_service

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


# --- Platform Owner: pick any society, see its full report (v1.8) ---
# society_id is explicit here rather than derived from current.society_id
# (a Platform Owner has none of their own) — same pattern already used
# throughout societies.py's /{society_id}/... endpoints.

@router.get("/platform/{society_id}/overview", response_model=SocietyPeopleOverviewOut)
async def platform_society_overview(
    society_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> SocietyPeopleOverviewOut:
    return await report_service.society_people_overview(db, society_id)


@router.get("/platform/{society_id}/maintenance-summary", response_model=MaintenanceSummaryOut)
async def platform_maintenance_summary(
    society_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> MaintenanceSummaryOut:
    return await report_service.platform_maintenance_summary(db, society_id)


@router.get("/platform/{society_id}/manager-performance", response_model=list[ManagerPerformanceOut])
async def platform_manager_performance(
    society_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> list[ManagerPerformanceOut]:
    return await report_service.manager_performance(db, society_id)


@router.get("/platform/{society_id}/balance", response_model=BalanceSummaryOut)
async def platform_balance(
    society_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> BalanceSummaryOut:
    summary = await account_entry_service.balance_summary(db, society_id)
    return BalanceSummaryOut(**summary)
