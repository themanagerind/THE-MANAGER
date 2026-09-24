"""Admin change request service — two ways a society's Admin gets
replaced, both requiring unanimous Sub-admin sign-off:
  1. Platform Owner picks a brand-new outside person (create_admin_change_request).
  2. The Admin themselves resigns and picks an existing Resident/Sub-admin
     as their successor (create_resignation_request).
See app/models/identity.py's AdminChangeRequest/AdminChangeApproval
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
from app.models.identity import (
    AdminChangeApproval,
    AdminChangeRequest,
    Property,
    PropertyResident,
    Society,
    SocietyLocation,
    User,
    UserRole,
)
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


async def _reject_if_pending_request_exists(db: AsyncSession, society_id: uuid.UUID) -> None:
    existing = (
        await db.execute(
            select(AdminChangeRequest).where(
                AdminChangeRequest.society_id == society_id, AdminChangeRequest.status == RoleRequestStatus.PENDING
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An Admin-change request is already pending for this society"
        )


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
        "new_admin_email": req.new_admin_email, "new_admin_user_id": req.new_admin_user_id,
        "status": req.status, "initiated_by": req.initiated_by,
        "new_admin_id": req.new_admin_id, "created_at": req.created_at, "decided_at": req.decided_at,
        "approvals_total": total, "approvals_done": done,
    }


async def _finalize(db: AsyncSession, req: AdminChangeRequest) -> None:
    """Revokes the old Admin's ADMIN role, then either grants ADMIN to an
    existing user (resignation path, new_admin_user_id set) or creates a
    brand-new ACTIVE account for one (Platform Owner path) — either way
    ACTIVE immediately, no further gate. Caller commits; this only adds/
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

    if req.new_admin_user_id is not None:
        new_admin_id = req.new_admin_user_id
        already_admin = (
            await db.execute(
                select(UserRole).where(
                    UserRole.user_id == new_admin_id, UserRole.role == Role.ADMIN, UserRole.revoked_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        if already_admin is None:
            db.add(
                UserRole(
                    user_id=new_admin_id, role=Role.ADMIN, assigned_by=req.initiated_by,
                    assigned_at=datetime.now(timezone.utc),
                )
            )
    else:
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
        new_admin_id = new_admin.id
        db.add(
            UserRole(
                user_id=new_admin_id, role=Role.ADMIN, assigned_by=req.initiated_by,
                assigned_at=datetime.now(timezone.utc),
            )
        )

    req.new_admin_id = new_admin_id
    req.status = RoleRequestStatus.APPROVED
    req.decided_at = datetime.now(timezone.utc)


async def _create_pending_or_finalized(
    db: AsyncSession, req: AdminChangeRequest, society_id: uuid.UUID
) -> dict:
    """Shared tail of both create_* functions below — add approval rows
    (or finalize immediately if there's no one to approve), commit,
    return the dict view."""
    subadmins = await _active_subadmins(db, society_id)
    if not subadmins:
        # No Sub-admin exists to approve — the initiator's decision is
        # final on its own, same reasoning as elsewhere in this app: no
        # one to review means nothing is held up waiting for review.
        await _finalize(db, req)
    else:
        for sa in subadmins:
            db.add(AdminChangeApproval(request_id=req.id, sub_admin_id=sa.id))

    await db.commit()
    await db.refresh(req)
    return await _as_dict(db, req)


async def _validate_existing_candidate(
    db: AsyncSession, society_id: uuid.UUID, candidate_id: uuid.UUID, exclude_id: uuid.UUID | None = None
) -> User:
    """Shared validation for picking an EXISTING user as the incoming
    Admin (Platform Owner's picker and an Admin's own resignation
    picker): must be an active user in this exact society, not the
    person being replaced, and currently hold RESIDENT or SUB_ADMIN."""
    candidate = (
        await db.execute(
            select(User).where(User.id == candidate_id, User.society_id == society_id, User.status == UserStatus.ACTIVE)
        )
    ).scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found in this society")
    if exclude_id is not None and candidate.id == exclude_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Can't pick yourself as your own successor")

    has_role = (
        await db.execute(
            select(UserRole).where(
                UserRole.user_id == candidate.id, UserRole.role.in_([Role.RESIDENT, Role.SUB_ADMIN]),
                UserRole.revoked_at.is_(None),
            )
        )
    ).first()
    if has_role is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Candidate must be an active Resident or Sub-admin in this society"
        )
    return candidate


async def create_admin_change_request(
    db: AsyncSession, body: AdminChangeRequestIn, initiated_by: uuid.UUID
) -> dict:
    """Platform Owner replaces a society's Admin, either by picking an
    existing Resident/Sub-admin (new_admin_user_id — the normal path,
    powered by the Wing/Row + search picker) or by entering a brand-new
    outside person's details by hand (the three manual fields — for
    someone with no account in the system yet)."""
    society = (await db.execute(select(Society).where(Society.id == body.society_id))).scalar_one_or_none()
    if society is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Society not found")

    old_admin = await _current_admin(db, body.society_id)
    if old_admin is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This society has no active Admin yet — use the normal Admin signup instead",
        )

    await _reject_if_pending_request_exists(db, body.society_id)

    if body.new_admin_user_id is not None:
        candidate = await _validate_existing_candidate(
            db, body.society_id, body.new_admin_user_id, exclude_id=old_admin.id
        )
        req = AdminChangeRequest(
            society_id=body.society_id, old_admin_id=old_admin.id, new_admin_full_name=candidate.full_name,
            new_admin_mobile=candidate.mobile, new_admin_email=candidate.email, new_admin_user_id=candidate.id,
            status=RoleRequestStatus.PENDING, initiated_by=initiated_by, created_at=datetime.now(timezone.utc),
        )
    else:
        if not body.new_admin_full_name or not body.new_admin_mobile:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Provide either new_admin_user_id or new_admin_full_name + new_admin_mobile",
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

    return await _create_pending_or_finalized(db, req, body.society_id)


async def list_resignation_candidates(
    db: AsyncSession,
    society_id: uuid.UUID,
    exclude_user_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
) -> list[dict]:
    """Every active Resident/Sub-admin in a society that can be picked as
    the new Admin — used by both the Admin's own resignation picker
    (exclude_user_id=self) and the Platform Owner's Change Admin picker
    (no exclusion, any society). SUB_ADMIN is shown instead of RESIDENT
    for someone holding both (subadmin_service.promote_to_subadmin
    always adds SUB_ADMIN alongside an existing RESIDENT, never instead
    of it). Left-joins the candidate's active property link so the
    picker can be filtered by Wing/Row (location_id) and each row can
    show its floor/flat number — a candidate with no active property
    link still appears (house/floor/location come back None) unless
    location_id narrows the query, in which case only linked candidates
    under that Wing/Row match."""
    query = (
        select(
            User.id, User.full_name, User.mobile, UserRole.role,
            Property.house_number, Property.floor_number, SocietyLocation.id, SocietyLocation.name,
        )
        .join(UserRole, UserRole.user_id == User.id)
        .outerjoin(
            PropertyResident,
            (PropertyResident.resident_id == User.id) & (PropertyResident.is_active.is_(True)),
        )
        .outerjoin(Property, Property.id == PropertyResident.property_id)
        .outerjoin(SocietyLocation, SocietyLocation.id == Property.location_id)
        .where(
            User.society_id == society_id, User.status == UserStatus.ACTIVE,
            UserRole.role.in_([Role.RESIDENT, Role.SUB_ADMIN]), UserRole.revoked_at.is_(None),
        )
    )
    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)
    if location_id is not None:
        query = query.where(SocietyLocation.id == location_id)

    rows = (await db.execute(query)).all()
    by_user: dict[uuid.UUID, dict] = {}
    for user_id, full_name, mobile, role, house_number, floor_number, loc_id, loc_name in rows:
        current = by_user.get(user_id)
        # Prefer a SUB_ADMIN-labeled row over a RESIDENT one for the same
        # user, and prefer a row that actually has a property link over
        # one that doesn't — otherwise keep the first match.
        if current is None or (role == Role.SUB_ADMIN and current["role_label"] != Role.SUB_ADMIN.value) or (
            current["house_number"] is None and house_number is not None
        ):
            by_user[user_id] = {
                "id": user_id, "full_name": full_name, "mobile": mobile, "role_label": role.value,
                "house_number": house_number, "floor_number": floor_number,
                "location_id": loc_id, "location_name": loc_name,
            }
    return sorted(by_user.values(), key=lambda r: r["full_name"])


async def create_resignation_request(
    db: AsyncSession, society_id: uuid.UUID, old_admin_id: uuid.UUID, new_admin_user_id: uuid.UUID
) -> dict:
    """The Admin themselves resigns, picking an existing Resident/Sub-
    admin as their successor — society_id/old_admin_id are the caller's
    own (from the auth token), not user input."""
    await _reject_if_pending_request_exists(db, society_id)

    candidate = await _validate_existing_candidate(db, society_id, new_admin_user_id, exclude_id=old_admin_id)

    req = AdminChangeRequest(
        society_id=society_id, old_admin_id=old_admin_id, new_admin_full_name=candidate.full_name,
        new_admin_mobile=candidate.mobile, new_admin_email=candidate.email, new_admin_user_id=candidate.id,
        status=RoleRequestStatus.PENDING, initiated_by=old_admin_id, created_at=datetime.now(timezone.utc),
    )
    db.add(req)
    await db.flush()

    return await _create_pending_or_finalized(db, req, society_id)


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


async def list_role_history(db: AsyncSession, society_id: uuid.UUID) -> list[dict]:
    """Every ADMIN/SUB_ADMIN role assignment a society has ever had,
    active or long since revoked — user_roles.assigned_at/revoked_at IS
    the work-period history, this just surfaces it, newest first."""
    rows = (
        await db.execute(
            select(UserRole.id, User.full_name, User.mobile, UserRole.role, UserRole.assigned_at, UserRole.revoked_at)
            .join(User, User.id == UserRole.user_id)
            .where(User.society_id == society_id, UserRole.role.in_([Role.ADMIN, Role.SUB_ADMIN]))
            .order_by(UserRole.assigned_at.desc())
        )
    ).all()
    return [
        {"id": r[0], "full_name": r[1], "mobile": r[2], "role": r[3], "assigned_at": r[4], "revoked_at": r[5]}
        for r in rows
    ]
