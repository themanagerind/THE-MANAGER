"""
Self-service profile — GET/PATCH /users/me. Every role uses the same two
functions here (a Platform Owner, Admin, Sub-admin, Manager, Resident or
Guard editing their own name/email is the same operation regardless of
which dashboard they're viewing it from), so this lives in its own small
module rather than duplicated per-role.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role
from app.models.identity import User, UserRole
from app.schemas.user import ProfileUpdateIn
from app.services import upload_service


async def _active_roles_for(db: AsyncSession, user_id: uuid.UUID) -> list[Role]:
    rows = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.revoked_at.is_(None))
        )
    ).scalars().all()
    return [Role(r.role) for r in rows]


async def _get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


async def get_profile(db: AsyncSession, user_id: uuid.UUID) -> tuple[User, list[Role]]:
    user = await _get_user_or_404(db, user_id)
    return user, await _active_roles_for(db, user_id)


async def update_profile(db: AsyncSession, user_id: uuid.UUID, body: ProfileUpdateIn) -> tuple[User, list[Role]]:
    user = await _get_user_or_404(db, user_id)
    user.full_name = body.full_name
    user.email = body.email
    await db.commit()
    await db.refresh(user)
    return user, await _active_roles_for(db, user_id)


async def update_avatar(db: AsyncSession, user_id: uuid.UUID, storage_key: str) -> tuple[User, list[Role]]:
    user = await _get_user_or_404(db, user_id)
    old_key = user.avatar_key
    user.avatar_key = storage_key
    await db.commit()
    await db.refresh(user)
    if old_key:
        upload_service.delete_avatar_file(old_key)
    return user, await _active_roles_for(db, user_id)


async def remove_avatar(db: AsyncSession, user_id: uuid.UUID) -> tuple[User, list[Role]]:
    user = await _get_user_or_404(db, user_id)
    old_key = user.avatar_key
    user.avatar_key = None
    await db.commit()
    await db.refresh(user)
    if old_key:
        upload_service.delete_avatar_file(old_key)
    return user, await _active_roles_for(db, user_id)
