"""
Sub-admin service — Section 6 (Admin promotes Resident, assigns scope),
Section 7 (Sub-admin scope, resignation), Section 26 (resignation flow).
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, RoleRequestStatus, RoleRequestType, UserStatus
from app.models.identity import RoleRequest, SocietyLocation, SubAdminScope, User, UserRole
from app.services.scope_service import user_has_active_role


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
    await db.commit()
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

    scope = SubAdminScope(
        society_id=society_id,
        sub_admin_id=sub_admin_id,
        location_id=location_id,
        assigned_by=assigned_by,
        assigned_at=datetime.now(timezone.utc),
    )
    db.add(scope)
    await db.commit()
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
