"""
Sub-admin service — Section 6 (Admin promotes Resident, assigns scope),
Section 7 (Sub-admin scope, resignation), Section 26 (resignation flow).
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, RoleRequestStatus, RoleRequestType, UserStatus
from app.models.identity import RoleRequest, SocietyLocation, SubAdminScope, User, UserRole
from app.services import expense_bill_service
from app.services.scope_service import active_subadmin_ids, user_has_active_role


async def _reject_if_locations_already_scoped(
    db: AsyncSession, location_ids: list[uuid.UUID], excluding_sub_admin_id: uuid.UUID
) -> None:
    """Section 7: at most one active Sub-admin per Wing/Row — a Wing
    already covered by someone else can't be handed to a second person
    too; the DB's own ux_sub_admin_scopes_location_active index is the
    final backstop, this is just the clean error before hitting it.
    Re-promoting the SAME resident onto a location they already hold
    isn't a conflict (excluded here) — ux_sub_admin_scopes_active handles
    that case instead (already-scoped locations never reach this
    function from the "unassigned only" picker anyway, see
    PromoteModal.tsx)."""
    rows = (
        await db.execute(
            select(SocietyLocation.name)
            .join(SubAdminScope, SubAdminScope.location_id == SocietyLocation.id)
            .where(
                SubAdminScope.location_id.in_(location_ids),
                SubAdminScope.sub_admin_id != excluding_sub_admin_id,
                SubAdminScope.revoked_at.is_(None),
            )
        )
    ).scalars().all()
    if rows:
        names = ", ".join(sorted(set(rows)))
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Already has an active Sub-admin, remove them first: {names}",
        )


async def promote_to_subadmin(
    db: AsyncSession,
    society_id: uuid.UUID,
    resident_id: uuid.UUID,
    location_ids: list[uuid.UUID],
    promoted_by: uuid.UUID,
) -> list[SubAdminScope]:
    resident = (
        await db.execute(
            select(User).where(
                User.id == resident_id, User.society_id == society_id, User.status == UserStatus.ACTIVE
            )
        )
    ).scalar_one_or_none()
    if resident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Active resident not found in this society")

    if not location_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "At least one location must be assigned")

    # Verify every location belongs to this society (tenant isolation).
    locations = (
        await db.execute(
            select(SocietyLocation).where(
                SocietyLocation.id.in_(location_ids), SocietyLocation.society_id == society_id
            )
        )
    ).scalars().all()
    if len(locations) != len(set(location_ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or more locations not found in this society")

    await _reject_if_locations_already_scoped(db, location_ids, excluding_sub_admin_id=resident_id)

    # Dual-role: add SUB_ADMIN alongside any existing RESIDENT role — never
    # remove/replace existing roles (Section 4.3/4.4).
    existing_subadmin_role = (
        await db.execute(
            select(UserRole).where(
                UserRole.user_id == resident_id,
                UserRole.role == Role.SUB_ADMIN,
                UserRole.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing_subadmin_role is None:
        db.add(
            UserRole(
                user_id=resident_id,
                role=Role.SUB_ADMIN,
                assigned_by=promoted_by,
                assigned_at=datetime.now(timezone.utc),
            )
        )

    now = datetime.now(timezone.utc)
    scopes = [
        SubAdminScope(
            society_id=society_id,
            sub_admin_id=resident_id,
            location_id=loc_id,
            assigned_by=promoted_by,
            assigned_at=now,
        )
        for loc_id in location_ids
    ]
    db.add_all(scopes)
    try:
        await db.commit()
    except IntegrityError:
        # Race: someone else was granted one of these locations between
        # the check above and this commit, or the resident already held
        # one of them (re-selecting an already-assigned location).
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "One or more of these Wings/Rows already has an active Sub-admin, or is already assigned to this person.",
        )
    for s in scopes:
        await db.refresh(s)
    return scopes


async def demote_subadmin(db: AsyncSession, society_id: uuid.UUID, sub_admin_id: uuid.UUID) -> None:
    """Admin directly removes someone's Sub-admin role — the only demote
    path before this was the Sub-admin resigning themselves (submit_
    resignation) and the Admin approving that (decide_resignation), which
    only works if the Sub-admin agrees; an Admin promotes unilaterally, so
    they need a way to undo that unilaterally too. Revokes the SUB_ADMIN
    role AND every active scope together (same cleanup decide_resignation's
    approve branch does) — leaving the role revoked but scopes active (or
    vice versa) would be a broken half-state: a scope-less Sub-admin still
    counts toward Proposal/Expense Bill thresholds (scope_service.
    active_subadmin_ids is role-based, not scope-based), while a role-less
    one with leftover scope rows is just dead data. RESIDENT role (if
    held) is untouched — dual-role, same as resignation."""
    # Tenant-isolated existence check (same helper assign_additional_scope
    # uses) — a bare UserRole lookup alone can't verify society_id, since
    # UserRole doesn't carry one.
    if not await user_has_active_role(db, sub_admin_id, society_id, Role.SUB_ADMIN):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "This person doesn't currently hold an active Sub-admin role in this society"
        )

    # Audit fix: demoting the LAST active Sub-admin while an expense bill is
    # PENDING_APPROVAL would leave it permanently stuck — 0 active means the
    # 100% threshold can never be met, and decide_approval requires an
    # active Sub-admin caller, so no one would be left who's even allowed
    # to reject it either.
    active_ids = await active_subadmin_ids(db, society_id)
    if active_ids == {sub_admin_id} and await expense_bill_service.has_pending_bills(db, society_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot remove the only active Sub-admin while an expense bill is pending approval — "
            "have it approved/rejected, or promote another Sub-admin, first",
        )

    role = (
        await db.execute(
            select(UserRole).where(
                UserRole.user_id == sub_admin_id, UserRole.role == Role.SUB_ADMIN, UserRole.revoked_at.is_(None)
            )
        )
    ).scalar_one()

    now = datetime.now(timezone.utc)
    role.revoked_at = now

    scopes = (
        await db.execute(
            select(SubAdminScope).where(
                SubAdminScope.society_id == society_id,
                SubAdminScope.sub_admin_id == sub_admin_id,
                SubAdminScope.revoked_at.is_(None),
            )
        )
    ).scalars().all()
    for scope in scopes:
        scope.revoked_at = now

    await db.commit()


async def assign_additional_scope(
    db: AsyncSession, society_id: uuid.UUID, sub_admin_id: uuid.UUID, location_id: uuid.UUID, assigned_by: uuid.UUID
) -> SubAdminScope:
    # HIGH fix (audit round-8): verify the target actually holds an active
    # Sub-admin role in this society — the composite FK only guarantees
    # same-society, not correct-role/active.
    if not await user_has_active_role(db, sub_admin_id, society_id, Role.SUB_ADMIN):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Target user does not hold an active Sub-admin role in this society"
        )

    location = (
        await db.execute(
            select(SocietyLocation).where(
                SocietyLocation.id == location_id, SocietyLocation.society_id == society_id
            )
        )
    ).scalar_one_or_none()
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found in this society")

    await _reject_if_locations_already_scoped(db, [location_id], excluding_sub_admin_id=sub_admin_id)

    scope = SubAdminScope(
        society_id=society_id,
        sub_admin_id=sub_admin_id,
        location_id=location_id,
        assigned_by=assigned_by,
        assigned_at=datetime.now(timezone.utc),
    )
    db.add(scope)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This Wing/Row already has an active Sub-admin, or is already assigned to this person.",
        )
    await db.refresh(scope)
    return scope


async def revoke_scope(db: AsyncSession, society_id: uuid.UUID, scope_id: uuid.UUID) -> SubAdminScope:
    scope = (
        await db.execute(
            select(SubAdminScope).where(SubAdminScope.id == scope_id, SubAdminScope.society_id == society_id)
        )
    ).scalar_one_or_none()
    if scope is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scope not found in this society")
    if scope.revoked_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Scope already revoked")
    scope.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(scope)
    return scope


async def list_subadmin_scopes(
    db: AsyncSession, society_id: uuid.UUID, sub_admin_id: uuid.UUID
) -> list[SubAdminScope]:
    return (
        await db.execute(
            select(SubAdminScope).where(
                SubAdminScope.society_id == society_id,
                SubAdminScope.sub_admin_id == sub_admin_id,
                SubAdminScope.revoked_at.is_(None),
            )
        )
    ).scalars().all()


async def list_all_assignments(db: AsyncSession, society_id: uuid.UUID) -> list[dict]:
    """Every active Sub-admin scope in the society, denormalized with the
    Sub-admin's and location's own name/mobile — powers the Assign
    Sub-admin page's "Current Sub-admins" overview (GET /subadmins).
    Returns plain dicts (SubAdminAssignmentOut(**row)) since this is a
    join projection, not a single model."""
    rows = (
        await db.execute(
            select(
                SubAdminScope.id, SubAdminScope.sub_admin_id, User.full_name, User.mobile,
                SubAdminScope.location_id, SocietyLocation.name, SocietyLocation.location_type,
                SubAdminScope.assigned_at,
            )
            .join(User, User.id == SubAdminScope.sub_admin_id)
            .join(SocietyLocation, SocietyLocation.id == SubAdminScope.location_id)
            .where(SubAdminScope.society_id == society_id, SubAdminScope.revoked_at.is_(None))
            .order_by(SocietyLocation.name)
        )
    ).all()
    return [
        {
            "scope_id": r[0], "sub_admin_id": r[1], "sub_admin_name": r[2], "sub_admin_mobile": r[3],
            "location_id": r[4], "location_name": r[5], "location_type": r[6], "assigned_at": r[7],
        }
        for r in rows
    ]


async def submit_resignation(
    db: AsyncSession, society_id: uuid.UUID, sub_admin_id: uuid.UUID, reason: str | None
) -> RoleRequest:
    active_role = (
        await db.execute(
            select(UserRole).where(
                UserRole.user_id == sub_admin_id,
                UserRole.role == Role.SUB_ADMIN,
                UserRole.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if active_role is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "User does not currently hold an active Sub-admin role")

    existing_pending = (
        await db.execute(
            select(RoleRequest).where(
                RoleRequest.user_id == sub_admin_id,
                RoleRequest.request_type == RoleRequestType.SUB_ADMIN_RESIGNATION,
                RoleRequest.status == RoleRequestStatus.PENDING,
            )
        )
    ).scalar_one_or_none()
    if existing_pending is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A resignation request is already pending")

    req = RoleRequest(
        user_id=sub_admin_id,
        society_id=society_id,
        request_type=RoleRequestType.SUB_ADMIN_RESIGNATION,
        status=RoleRequestStatus.PENDING,
        reason=reason,
        created_at=datetime.now(timezone.utc),
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return req


async def list_pending_resignations(db: AsyncSession, society_id: uuid.UUID) -> list[RoleRequest]:
    return (
        await db.execute(
            select(RoleRequest).where(
                RoleRequest.society_id == society_id,
                RoleRequest.request_type == RoleRequestType.SUB_ADMIN_RESIGNATION,
                RoleRequest.status == RoleRequestStatus.PENDING,
            )
        )
    ).scalars().all()


async def decide_resignation(
    db: AsyncSession,
    society_id: uuid.UUID,
    request_id: uuid.UUID,
    approve: bool,
    decision_reason: str | None,
    reviewed_by: uuid.UUID,
) -> RoleRequest:
    req = (
        await db.execute(
            select(RoleRequest).where(RoleRequest.id == request_id, RoleRequest.society_id == society_id)
        )
    ).scalar_one_or_none()
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resignation request not found in this society")
    if req.status != RoleRequestStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Request is already {req.status.value}")

    # Audit fix: same guard as demote_subadmin — approving the resignation
    # of the LAST active Sub-admin while an expense bill is pending would
    # leave it permanently stuck.
    if approve:
        active_ids = await active_subadmin_ids(db, society_id)
        if active_ids == {req.user_id} and await expense_bill_service.has_pending_bills(db, society_id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Cannot approve this resignation while it's the only active Sub-admin and an expense bill is "
                "pending approval — have it approved/rejected, or promote another Sub-admin, first",
            )

    now = datetime.now(timezone.utc)
    req.status = RoleRequestStatus.APPROVED if approve else RoleRequestStatus.REJECTED
    req.reviewed_by = reviewed_by
    req.reviewed_at = now
    req.decision_reason = decision_reason

    if approve:
        # Revoke the SUB_ADMIN role AND every active scope — RESIDENT role
        # (if held) is untouched (dual-role: resignation only removes the
        # Sub-admin capability, Section 4.3).
        subadmin_role = (
            await db.execute(
                select(UserRole).where(
                    UserRole.user_id == req.user_id,
                    UserRole.role == Role.SUB_ADMIN,
                    UserRole.revoked_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if subadmin_role is not None:
            subadmin_role.revoked_at = now

        scopes = (
            await db.execute(
                select(SubAdminScope).where(
                    SubAdminScope.sub_admin_id == req.user_id, SubAdminScope.revoked_at.is_(None)
                )
            )
        ).scalars().all()
        for scope in scopes:
            scope.revoked_at = now

    await db.commit()
    await db.refresh(req)
    return req
