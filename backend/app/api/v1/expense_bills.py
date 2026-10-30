"""Expense bills endpoints — Section 23."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.expense_bill import (
    ExpenseBillApprovalOut,
    ExpenseBillCreateIn,
    ExpenseBillDecisionIn,
    ExpenseBillOut,
    ExpenseBillStatusDetailOut,
)
from app.schemas.pagination import Page, Pagination, pagination_params
from app.services import expense_bill_service, upload_service

router = APIRouter(prefix="/expense-bills", tags=["expense-bills"])


@router.post("/draft", response_model=ExpenseBillOut)
async def create_draft(
    body: ExpenseBillCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.MANAGER))],
) -> ExpenseBillOut:
    """Manager creates a draft (Section 23)."""
    bill = await expense_bill_service.create_draft(db, current.society_id, current.user_id, body)
    return ExpenseBillOut.model_validate(bill)


@router.post("", response_model=ExpenseBillOut)
async def create_and_finalize(
    body: ExpenseBillCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> ExpenseBillOut:
    """Admin creates directly, skipping the draft step."""
    bill = await expense_bill_service.create_and_finalize(db, current.society_id, current.user_id, body)
    return ExpenseBillOut.model_validate(bill)


@router.post("/{bill_id}/finalize", response_model=ExpenseBillOut)
async def finalize(
    bill_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> ExpenseBillOut:
    """Admin finalizes a Manager-created draft (Section 23)."""
    bill = await expense_bill_service.finalize_draft(db, current.society_id, bill_id, current.user_id)
    return ExpenseBillOut.model_validate(bill)


@router.get("", response_model=Page[ExpenseBillOut])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[
        CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.MANAGER))
    ],
    pagination: Annotated[Pagination, Depends(pagination_params)],
) -> Page[ExpenseBillOut]:
    bills, total = await expense_bill_service.list_bills(db, current.society_id, pagination.skip, pagination.limit)
    return Page(items=[ExpenseBillOut.model_validate(b) for b in bills], total=total, skip=pagination.skip, limit=pagination.limit)


@router.get("/{bill_id}/image")
async def get_bill_image(
    bill_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[
        CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.MANAGER))
    ],
) -> FileResponse:
    """The only way to read a bill image's bytes — same authorization as
    the bill's own detail endpoint (society-scoped, no public mount)."""
    bill = await expense_bill_service.get_bill(db, current.society_id, bill_id)
    if not bill.bill_image_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bill image uploaded for this bill")
    path = upload_service.resolve_expense_bill_image_path(bill.bill_image_key)
    return FileResponse(path)


@router.get("/{bill_id}", response_model=ExpenseBillStatusDetailOut)
async def get_detail(
    bill_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[
        CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.MANAGER))
    ],
) -> ExpenseBillStatusDetailOut:
    bill = await expense_bill_service.get_bill(db, current.society_id, bill_id)
    detail = await expense_bill_service.status_detail(db, bill)
    return ExpenseBillStatusDetailOut(bill=ExpenseBillOut.model_validate(bill), **detail)


@router.post("/{bill_id}/decision", response_model=ExpenseBillApprovalOut)
async def decide(
    bill_id: uuid.UUID,
    body: ExpenseBillDecisionIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.SUB_ADMIN))],
) -> ExpenseBillApprovalOut:
    """100% of active Sub-admins required to APPROVE; any single REJECT is
    immediate and final (Section 23)."""
    approval = await expense_bill_service.decide_approval(
        db, current.society_id, current.user_id, bill_id, body.decision, body.reason
    )
    return ExpenseBillApprovalOut.model_validate(approval)
