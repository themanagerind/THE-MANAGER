"""Account report endpoints — Section 13.0/13.1."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.account_entry import (
    AccountEntryCreateIn,
    AccountEntryOut,
    AccountEntryUpdateIn,
    BalanceSummaryOut,
)
from app.schemas.pagination import Page, Pagination, pagination_params
from app.services import account_entry_service

router = APIRouter(prefix="/account-entries", tags=["account-entries"])


@router.post("", response_model=AccountEntryOut)
async def create(
    body: AccountEntryCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> AccountEntryOut:
    """Section 13.1 — sirf Admin entry create kar sakta hai."""
    entry = await account_entry_service.create_manual_entry(
        db, current.society_id, current.user_id, body.entry_type, body.title,
        body.description, body.amount, body.entry_date,
    )
    return AccountEntryOut.model_validate(entry)


@router.get("", response_model=Page[AccountEntryOut])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[
        CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.MANAGER, Role.RESIDENT))
    ],
    pagination: Annotated[Pagination, Depends(pagination_params)],
) -> Page[AccountEntryOut]:
    """Section 13.1 — sabhi Residents ko visible, read-only."""
    entries, total = await account_entry_service.list_entries(
        db, current.society_id, pagination.skip, pagination.limit
    )
    return Page(items=[AccountEntryOut.model_validate(e) for e in entries], total=total, skip=pagination.skip, limit=pagination.limit)


@router.get("/balance", response_model=BalanceSummaryOut)
async def balance(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[
        CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.MANAGER, Role.RESIDENT))
    ],
) -> BalanceSummaryOut:
    summary = await account_entry_service.balance_summary(db, current.society_id)
    return BalanceSummaryOut(**summary)


@router.patch("/{entry_id}", response_model=AccountEntryOut)
async def edit(
    entry_id: uuid.UUID,
    body: AccountEntryUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> AccountEntryOut:
    """Section 13.1 — edit history preserved, is_edited flag drives the
    'Edited' badge in the UI."""
    entry = await account_entry_service.edit_manual_entry(
        db, current.society_id, entry_id, current.user_id,
        body.title, body.description, body.amount, body.entry_date,
    )
    return AccountEntryOut.model_validate(entry)
