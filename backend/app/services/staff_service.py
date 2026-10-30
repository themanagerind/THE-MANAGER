"""Manager/Security Guard direct account creation.

Both roles are third-party hired staff, not Residents (no property link,
Section 4's dual-role requirement is ADMIN-specific) — the Admin hiring
them creates the account directly and it's ACTIVE immediately, same as
the Platform Owner's "brand-new outside person" path for replacing an
Admin (admin_change_service._finalize). Housekeeping/other staff types
are intentionally out of scope — they're a plain roster record, not a
login role, and aren't built here."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, UserStatus
from app.models.identity import User, UserRole
from app.schemas.staff import STAFF_ROLES


async def create_staff(
    db: AsyncSession, society_id: uuid.UUID, full_name: str, mobile: str, email: str | None,
    role: Role, created_by: uuid.UUID,
) -> dict:
    if role not in STAFF_ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "role must be MANAGER or SECURITY_GUARD")

    now = datetime.now(timezone.utc)
    user = User(
        society_id=society_id, full_name=full_name, mobile=mobile, email=email,
        status=UserStatus.ACTIVE, approved_by=created_by, approved_at=now,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Mobile number '{mobile}' is already in use in this society"
        ) from exc

    db.add(UserRole(user_id=user.id, role=role, assigned_by=created_by, assigned_at=now))
    await db.commit()
    return {
        "id": user.id, "society_id": society_id, "full_name": full_name, "mobile": mobile,
        "email": email, "role": role, "status": UserStatus.ACTIVE, "assigned_at": now,
    }


async def list_staff(db: AsyncSession, society_id: uuid.UUID) -> list[dict]:
    """Every active Manager/Security Guard in the society — the Admin's
    staff directory (GET /staff)."""
    rows = (
        await db.execute(
            select(
                User.id, User.full_name, User.mobile, User.email, User.status,
                UserRole.role, UserRole.assigned_at,
            )
            .join(UserRole, UserRole.user_id == User.id)
            .where(
                User.society_id == society_id,
                UserRole.role.in_(STAFF_ROLES),
                UserRole.revoked_at.is_(None),
            )
            .order_by(UserRole.assigned_at.desc())
        )
    ).all()
    return [
        {
            "id": r[0], "society_id": society_id, "full_name": r[1], "mobile": r[2], "email": r[3],
            "status": r[4], "role": r[5], "assigned_at": r[6],
        }
        for r in rows
    ]


async def remove_staff(db: AsyncSession, society_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Admin unilaterally removes every active Manager/Security Guard role
    this account holds in this society — same unilateral revoke pattern as
    subadmin_service.demote_subadmin (promotion here is unilateral too, so
    undoing it is)."""
    roles = (
        await db.execute(
            select(UserRole)
            .join(User, User.id == UserRole.user_id)
            .where(
                UserRole.user_id == user_id,
                UserRole.role.in_(STAFF_ROLES),
                UserRole.revoked_at.is_(None),
                User.society_id == society_id,
            )
        )
    ).scalars().all()
    if not roles:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "This person doesn't currently hold a Manager/Security Guard role in this society"
        )
    now = datetime.now(timezone.utc)
    for role in roles:
        role.revoked_at = now
    await db.commit()
