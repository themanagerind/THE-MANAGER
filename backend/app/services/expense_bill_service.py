"""
Expense bill service — Section 23.

Manager creates DRAFT -> Admin finalizes (DRAFT -> PENDING_APPROVAL, blocked
if 0 active Sub-admins exist) -> Sub-admins decide -> 100% APPROVE ->
APPROVED; any single REJECT -> REJECTED immediately.

Reactivation semantics (RESOLVED, confirmed): expense_bill_approvals rows
are NEVER deleted when a Sub-admin goes inactive — they simply stop/start
counting based on current active status (Section 49, active_subadmin_ids).
No code path here needs to handle "reactivation" specially — it falls out
naturally from recomputing the count live every time.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Decision, ExpenseBillStatus
from app.models.governance import ExpenseBill, ExpenseBillApproval
from app.schemas.expense_bill import ExpenseBillCreateIn
from app.services.scope_service import active_subadmin_ids


async def create_draft(
    db: AsyncSession, society_id: uuid.UUID, created_by: uuid.UUID, body: ExpenseBillCreateIn
) -> ExpenseBill:
    """Manager creates a draft — not yet sent for approval."""
    bill = ExpenseBill(
        society_id=society_id,
        title=body.title,
        description=body.description,
        amount=body.amount,
        category=body.category,
        bill_image_key=body.bill_image_key,
        status=ExpenseBillStatus.DRAFT,
        created_by=created_by,
    )
    db.add(bill)
    await db.commit()
    await db.refresh(bill)
    return bill


async def create_and_finalize(
    db: AsyncSession, society_id: uuid.UUID, created_by: uuid.UUID, body: ExpenseBillCreateIn
) -> ExpenseBill:
    """Admin creates directly, skipping the Manager-draft step — goes
    straight to PENDING_APPROVAL (still subject to the zero-active-subadmin
    block, Section 23 RESOLVED)."""
    if len(await active_subadmin_ids(db, society_id)) == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Cannot open for approval — society has 0 active Sub-admins"
        )
    now = datetime.now(timezone.utc)
    bill = ExpenseBill(
        society_id=society_id,
        title=body.title,
        description=body.description,
        amount=body.amount,
        category=body.category,
        bill_image_key=body.bill_image_key,
        status=ExpenseBillStatus.PENDING_APPROVAL,
        created_by=created_by,
        finalized_by=created_by,
        finalized_at=now,
    )
    db.add(bill)
    await db.commit()
    await db.refresh(bill)
    return bill


async def finalize_draft(
    db: AsyncSession, society_id: uuid.UUID, bill_id: uuid.UUID, finalized_by: uuid.UUID
) -> ExpenseBill:
    """Admin finalizes a Manager-created draft (Section 23)."""
    bill = await get_bill(db, society_id, bill_id)
    if bill.status != ExpenseBillStatus.DRAFT:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Bill is {bill.status.value}, not DRAFT")

    if len(await active_subadmin_ids(db, society_id)) == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Cannot open for approval — society has 0 active Sub-admins"
        )

    bill.status = ExpenseBillStatus.PENDING_APPROVAL
    bill.finalized_by = finalized_by
    bill.finalized_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(bill)
    return bill


async def has_pending_bills(db: AsyncSession, society_id: uuid.UUID) -> bool:
    """True if any expense bill in this society is still PENDING_APPROVAL —
    used by subadmin_service to block the last active Sub-admin from being
    removed (demote or resignation-approval). Every decision on a bill
    requires an active Sub-admin caller (Section 23), so dropping the
    active count to 0 while one is pending would leave it permanently
    stuck: unable to be approved (0 active means the 100% threshold can
    never be met) or rejected (no one left who's allowed to)."""
    result = (
        await db.execute(
            select(ExpenseBill.id)
            .where(ExpenseBill.society_id == society_id, ExpenseBill.status == ExpenseBillStatus.PENDING_APPROVAL)
            .limit(1)
        )
    ).first()
    return result is not None


async def get_bill(db: AsyncSession, society_id: uuid.UUID, bill_id: uuid.UUID) -> ExpenseBill:
    bill = (
        await db.execute(
            select(ExpenseBill).where(ExpenseBill.id == bill_id, ExpenseBill.society_id == society_id)
        )
    ).scalar_one_or_none()
    if bill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense bill not found in this society")
    return bill


async def list_bills(db: AsyncSession, society_id: uuid.UUID, skip: int = 0, limit: int = 20) -> tuple[list[ExpenseBill], int]:
    from sqlalchemy import func
    total = (await db.execute(select(func.count()).select_from(ExpenseBill).where(ExpenseBill.society_id == society_id))).scalar_one()
    rows = (
        await db.execute(
            select(ExpenseBill).where(ExpenseBill.society_id == society_id)
            .order_by(ExpenseBill.created_at.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()
    return rows, total


async def status_detail(db: AsyncSession, bill: ExpenseBill) -> dict:
    active_ids = await active_subadmin_ids(db, bill.society_id)
    approvals = (
        await db.execute(select(ExpenseBillApproval).where(ExpenseBillApproval.expense_bill_id == bill.id))
    ).scalars().all()
    approve_count = len(
        {a.sub_admin_id for a in approvals if a.decision == Decision.APPROVE} & active_ids
    )
    return {
        "approve_count": approve_count,
        "active_subadmin_count": len(active_ids),
        "approvals_needed": max(len(active_ids) - approve_count, 0),
    }


async def decide_approval(
    db: AsyncSession,
    society_id: uuid.UUID,
    sub_admin_id: uuid.UUID,
    bill_id: uuid.UUID,
    decision: Decision,
    reason: str | None,
) -> ExpenseBillApproval:
    # Row lock (Transactions — expense approval concurrency): serializes
    # concurrent decisions on the same bill so the "have we hit 100%?" /
    # "has someone already rejected?" checks below are always consistent —
    # prevents two simultaneous last-approvals both missing the 100% flip,
    # or a reject landing after approval already fired.
    bill = (
        await db.execute(
            select(ExpenseBill)
            .where(ExpenseBill.id == bill_id, ExpenseBill.society_id == society_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if bill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense bill not found in this society")
    if bill.status != ExpenseBillStatus.PENDING_APPROVAL:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Bill is {bill.status.value}, not open for approval")

    if decision == Decision.REJECT and not reason:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Rejection reason is mandatory")

    existing = (
        await db.execute(
            select(ExpenseBillApproval).where(
                ExpenseBillApproval.expense_bill_id == bill_id, ExpenseBillApproval.sub_admin_id == sub_admin_id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already decided on this bill")

    approval = ExpenseBillApproval(
        society_id=society_id,
        expense_bill_id=bill_id,
        sub_admin_id=sub_admin_id,
        decision=decision,
        reason=reason,
        decided_at=datetime.now(timezone.utc),
    )
    db.add(approval)
    await db.flush()

    if decision == Decision.REJECT:
        # A single reject is immediate and final (Section 23) — no need to
        # wait for the rest of the Sub-admins.
        bill.status = ExpenseBillStatus.REJECTED
    else:
        detail = await status_detail(db, bill)
        if detail["active_subadmin_count"] > 0 and detail["approve_count"] >= detail["active_subadmin_count"]:
            bill.status = ExpenseBillStatus.APPROVED
            # Redesign (user-requested): approval no longer auto-posts to
            # Accounts. Admin settles it manually from the Accounts screen
            # (account_entry_service.settle_expense_bill), picking a
            # heading and an amount capped at bill.amount — this bill just
            # becomes visible there once APPROVED, nothing more happens
            # here automatically.

    await db.commit()
    await db.refresh(approval)
    return approval
