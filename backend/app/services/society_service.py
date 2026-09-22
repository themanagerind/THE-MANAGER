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
from app.schemas.society import SocietyCreateIn, SocietySignupIn


async def create_society(db: AsyncSession, body: SocietyCreateIn) -> Society:
    """Platform Owner creates a society directly — this is the only path
    for a society to exist now that Admin signup targets an existing one
    instead of bundling a new society with it. Goes straight to ACTIVE:
    the Platform Owner creating it from their own dashboard IS the
    approval, there's no one else who needs to sign off on it."""
    existing = (
        await db.execute(select(Society).where(Society.code == body.code))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Society code already in use")

    society = Society(
        name=body.name, code=body.code, status=SocietyStatus.ACTIVE,
        address=body.address, city=body.city, state=body.state, pincode=body.pincode,
    )
    db.add(society)
    await db.commit()
    await db.refresh(society)
    return society


async def lookup_society_by_code(db: AsyncSession, code: str) -> Society | None:
    """Public lookup for the Admin/Resident signup forms — only returns an
    ACTIVE society (a PENDING or SUSPENDED one isn't accepting anyone
    signing up against it)."""
    return (
        await db.execute(
            select(Society).where(Society.code == code, Society.status == SocietyStatus.ACTIVE)
        )
    ).scalar_one_or_none()


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
    this endpoint is for subsequent SUSPENDED<->ACTIVE transitions.)

    Audit fix: the docstring's contract wasn't enforced — new_status was
    assigned unconditionally, so a Platform Owner could send PENDING at any
    time (ACTIVE -> PENDING, SUSPENDED -> PENDING), or "approve" an already
    non-PENDING society through this endpoint. PENDING is only ever reached
    via signup, and only ever left via /approve."""
    society = (await db.execute(select(Society).where(Society.id == society_id))).scalar_one_or_none()
    if society is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Society not found")

    if new_status == SocietyStatus.PENDING:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cannot set status to PENDING — that's the initial signup state, not a transition target",
        )
    if society.status == SocietyStatus.PENDING:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Society is still PENDING — use POST /societies/{id}/approve first",
        )

    society.status = new_status
    await db.commit()
    await db.refresh(society)
    return society
