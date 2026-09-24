"""Admin change request service — Platform Owner-initiated replacement of
a society's Admin, requiring unanimous Sub-admin sign-off. See
app/models/identity.py's AdminChangeRequest/AdminChangeApproval
docstrings for the full flow and app/schemas/admin_change.py for why
AdminChangeRequestOut is built as a plain dict, not model_validate.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, RoleRequestStatus, UserStatus
from app.models.identity import AdminChangeApproval, AdminChangeRequest, Society, User, UserRole
from app.schemas.admin_change import AdminChangeRequestIn


async def _current_admin(db: AsyncSession, society_id: uuid.UUID) -> User | None:
    return (
        await db.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .where(User.society_id == society_id, UserRole.role == Role.ADMIN, UserRole.revoked_at.is_(None))
        )
    ).scalar_one_or_none()


async def _active_subadmins(db: AsyncSession, society_id: uuid.UUID) -> list[User]:
    return (
        await db.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .where(User.society_id == society_id, UserRole.role == Role.SUB_ADMIN, UserRole.revoked_at.is_(None))
        )
    ).scalars().all()


async def _progress(db: AsyncSession, request_id: uuid.UUID) -> tuple[int, int]:
    total = (
        await db.execute(
            select(func.count()).select_from(AdminChangeApproval).where(AdminChangeApproval.request_id == request_id)
        )
    ).scalar_one()
    done = (
        await db.execute(
            select(func.count()).select_from(AdminChangeApproval).where(
                AdminChangeApproval.request_id == request_id, AdminChangeApproval.approved.is_(True)
            )
        )
    ).scalar_one()
    return total, done


async def _as_dict(db: AsyncSession, req: AdminChangeRequest) -> dict:
    total, done = await _progress(db, req.id)
    return {
        "id": req.id, "society_id": req.society_id, "old_admin_id": req.old_admin_id,
        "new_admin_full_name": req.new_admin_full_name, "new_admin_mobile": req.new_admin_mobile,
        "new_admin_email": req.new_admin_email, "status": req.status, "initiated_by": req.initiated_by,
        "new_admin_id": req.new_admin_id, "created_at": req.created_at, "decided_at": req.decided_at,
        "approvals_total": total, "approvals_done": done,
    }


async def _finalize(db: AsyncSession, req: AdminChangeRequest) -> None:
    """Revokes the old Admin's ADMIN role and creates the new one, ACTIVE
    immediately — Platform Owner + unanimous Sub-admin consent already IS
    the approval, so no further gate. Caller commits; this only adds/
    flushes. The old role's revoke is flushed BEFORE the new role is
    added so the one-Admin-per-society DB trigger (0008_admin_change)
    sees it within the same transaction and doesn't reject the new row."""
    old_role = (
        await db.execute(
            select(UserRole).where(
                UserRole.user_id == req.old_admin_id, UserRole.role == Role.ADMIN, UserRole.revoked_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if old_role is not None:
        old_role.revoked_at = datetime.now(timezone.utc)
        await db.flush()

    new_admin = User(
        society_id=req.society_id, full_name=req.new_admin_full_name, mobile=req.new_admin_mobile,
        email=req.new_admin_email, status=UserStatus.ACTIVE, approved_by=req.initiated_by,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(new_admin)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Could not finalize: mobile number '{req.new_admin_mobile}' is already in use in this society",
        ) from exc

    db.add(
        UserRole(user_id=new_admin.id, role=Role.ADMIN, assigned_by=req.initiated_by, assigned_at=datetime.now(timezone.utc))
    )
    req.new_admin_id = new_admin.id
    req.status = RoleRequestStatus.APPROVED
    req.decided_at = datetime.now(timezone.utc)


async def create_admin_change_request(
    db: AsyncSession, body: AdminChangeRequestIn, initiated_by: uuid.UUID
) -> dict:
    society = (await db.execute(select(Society).where(Society.id == body.society_id))).scalar_one_or_none()
    if society is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Society not found")

    old_admin = await _current_admin(db, body.society_id)
    if old_admin is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This society has no active Admin yet — use the normal Admin signup instead",
        )

    duplicate_mobile = (
        await db.execute(
            select(User).where(User.society_id == body.society_id, User.mobile == body.new_admin_mobile)
        )
    ).scalar_one_or_none()
    if duplicate_mobile is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This mobile number already has an account in this society"
        )

    req = AdminChangeRequest(
        society_id=body.society_id, old_admin_id=old_admin.id, new_admin_full_name=body.new_admin_full_name,
        new_admin_mobile=body.new_admin_mobile, new_admin_email=body.new_admin_email,
        status=RoleRequestStatus.PENDING, initiated_by=initiated_by, created_at=datetime.now(timezone.utc),
    )
    db.add(req)
    await db.flush()  # need req.id before adding approval rows / finalizing

    subadmins = await _active_subadmins(db, body.society_id)
    if not subadmins:
        # No Sub-admin exists to approve — Platform Owner's decision is
        # final on its own, same reasoning as elsewhere in this app: no
        # one to review means nothing is held up waiting for review.
        await _finalize(db, req)
    else:
        for sa in subadmins:
            db.add(AdminChangeApproval(request_id=req.id, sub_admin_id=sa.id))

    await db.commit()
    await db.refresh(req)
    return await _as_dict(db, req)


async def list_admin_change_requests(db: AsyncSession) -> list[dict]:
    """Platform Owner's own view — every request across every society,
    newest first."""
    reqs = (
        await db.execute(select(AdminChangeRequest).order_by(AdminChangeRequest.created_at.desc()))
    ).scalars().all()
    return [await _as_dict(db, r) for r in reqs]


async def list_pending_approvals_for_subadmin(
    db: AsyncSession, society_id: uuid.UUID, sub_admin_id: uuid.UUID
) -> list[dict]:
    rows = (
        await db.execute(
            select(
                AdminChangeApproval.id, AdminChangeRequest.id, AdminChangeRequest.society_id,
                AdminChangeRequest.new_admin_full_name, AdminChangeRequest.new_admin_mobile,
                AdminChangeApproval.decided_at,
            )
            .join(AdminChangeRequest, AdminChangeRequest.id == AdminChangeApproval.request_id)
            .where(
                AdminChangeApproval.sub_admin_id == sub_admin_id,
                AdminChangeApproval.approved.is_(None),
                AdminChangeRequest.society_id == society_id,
                AdminChangeRequest.status == RoleRequestStatus.PENDING,
            )
        )
    ).all()
    return [
        {
            "approval_id": r[0], "request_id": r[1], "society_id": r[2],
            "new_admin_full_name": r[3], "new_admin_mobile": r[4], "created_at": r[5] or datetime.now(timezone.utc),
        }
        for r in rows
    ]


async def decide_admin_change_approval(
    db: AsyncSession, society_id: uuid.UUID, sub_admin_id: uuid.UUID, request_id: uuid.UUID, approve: bool
) -> dict:
    approval = (
        await db.execute(
            select(AdminChangeApproval).where(
                AdminChangeApproval.request_id == request_id, AdminChangeApproval.sub_admin_id == sub_admin_id
            )
        )
    ).scalar_one_or_none()
    if approval is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such approval assigned to you")

    req = (await db.execute(select(AdminChangeRequest).where(AdminChangeRequest.id == request_id))).scalar_one_or_none()
    if req is None or req.society_id != society_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found in this society")
    if req.status != RoleRequestStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"This request is already {req.status.value}")
    if approval.approved is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "You've already responded to this request")

    approval.approved = approve
    approval.decided_at = datetime.now(timezone.utc)

    if not approve:
        # Unanimous consent required — a single reject cancels the whole
        # request. Other Sub-admins' still-pending rows are left as-is;
        # the request's own status is the source of truth for the UI.
        req.status = RoleRequestStatus.REJECTED
        req.decided_at = datetime.now(timezone.utc)
    else:
        total, done = await _progress(db, request_id)
        # This decision isn't flushed yet, so `done` doesn't count it —
        # +1 accounts for the row we just set above in this same
        # transaction.
        if done + 1 >= total:
            await _finalize(db, req)

    await db.commit()
    await db.refresh(approval)
    return await _as_dict(db, req)
