"""
Society service — Section 5 (Platform Owner), Section 6 (Admin), Section 25
(society status), Section 26 (Admin approval flow).
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, SocietyStatus, UserStatus
from app.models.identity import Society, User, UserRole
from app.schemas.society import SocietySignupIn


async def signup_society_and_admin(db: AsyncSession, body: SocietySignupIn) -> tuple[Society, User]:
    existing = (
        await db.execute(select(Society).where(Society.code == body.society_code))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Society code already in use")

    society = Society(
        name=body.society_name,
        code=body.society_code,
        status=SocietyStatus.PENDING,
        address=body.address,
        city=body.city,
        state=body.state,
        pincode=body.pincode,
    )
    db.add(society)
    await db.flush()  # get society.id without committing yet

    admin = User(
        society_id=society.id,
        full_name=body.admin_full_name,
        mobile=body.admin_mobile,
        email=body.admin_email,
        status=UserStatus.PENDING,
    )
    db.add(admin)
    await db.flush()

    # Role row created now, but login is gated on User.status == ACTIVE
    # regardless (get_current_user / resolve_login) — see Auth module.
    db.add(
        UserRole(
            user_id=admin.id,
            role=Role.ADMIN,
            assigned_by=None,  # self-signup, not assigned by another user
            assigned_at=datetime.now(timezone.utc),
        )
    )

    await db.commit()
    await db.refresh(society)
    await db.refresh(admin)
    return society, admin


async def list_societies(db: AsyncSession) -> list[Society]:
    return (await db.execute(select(Society))).scalars().all()


async def approve_society_and_admin(
    db: AsyncSession, society_id: uuid.UUID, approved_by: uuid.UUID
) -> Society:
    """Platform Owner approves a pending society — activates the society AND
    its founding Admin(s) together (Section 26: Admin approval flow)."""
    society = (await db.execute(select(Society).where(Society.id == society_id))).scalar_one_or_none()
    if society is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Society not found")
    if society.status != SocietyStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Society is already {society.status.value}")

    society.status = SocietyStatus.ACTIVE

    admins = (
        await db.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .where(
                User.society_id == society_id,
                UserRole.role == Role.ADMIN,
                UserRole.revoked_at.is_(None),
                User.status == UserStatus.PENDING,
            )
        )
    ).scalars().all()
    now = datetime.now(timezone.utc)
    for admin in admins:
        admin.status = UserStatus.ACTIVE
        admin.approved_by = approved_by
        admin.approved_at = now

    await db.commit()
    await db.refresh(society)
    return society


async def update_society_status(
    db: AsyncSession, society_id: uuid.UUID, new_status: SocietyStatus
) -> Society:
    """Section 25: PENDING -> ACTIVE -> SUSPENDED, Platform Owner controls it.
    (Use /approve for the initial PENDING->ACTIVE + admin-activation step;
    this endpoint is for subsequent SUSPENDED<->ACTIVE transitions.)"""
    society = (await db.execute(select(Society).where(Society.id == society_id))).scalar_one_or_none()
    if society is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Society not found")
    society.status = new_status
    await db.commit()
    await db.refresh(society)
    return society
