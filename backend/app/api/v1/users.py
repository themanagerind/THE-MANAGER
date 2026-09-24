"""Self-service profile — every authenticated role edits their own
full_name/email the same way, regardless of dashboard (see
app/services/user_service.py)."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, get_current_user, require_role
from app.models.identity import User
from app.models.enums import Role
from app.schemas.user import ProfileUpdateIn, UserOut
from app.services import upload_service, user_service

router = APIRouter(prefix="/users", tags=["users"])


def _user_out(user: User, roles: list[Role]) -> UserOut:
    # Built field-by-field rather than UserOut.model_validate(user) —
    # User.roles is a real (lazy) SQLAlchemy relationship, and
    # from_attributes would try to read it directly, triggering an
    # unawaited lazy-load outside an async context (MissingGreenlet).
    # `roles` here is the already-awaited active-roles list instead.
    return UserOut(
        id=user.id, society_id=user.society_id, full_name=user.full_name, mobile=user.mobile,
        email=user.email, status=user.status, roles=roles, created_at=user.created_at,
        has_avatar=user.avatar_key is not None,
    )


@router.get("/me", response_model=UserOut)
async def get_my_profile(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    user, roles = await user_service.get_profile(db, current.user_id)
    return _user_out(user, roles)


@router.patch("/me", response_model=UserOut)
async def update_my_profile(
    body: ProfileUpdateIn,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    user, roles = await user_service.update_profile(db, current.user_id, body)
    return _user_out(user, roles)


@router.post("/me/avatar", response_model=UserOut)
async def upload_my_avatar(
    file: UploadFile,
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT, Role.ADMIN, Role.SUB_ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    """Resident/Admin/Sub-admin self-service — replaces the sidebar's
    default logo with this photo (app/layouts/AppShell.tsx). Any previous
    photo is deleted from disk once the new one is saved."""
    storage_key = await upload_service.save_user_avatar(file, current.user_id)
    user, roles = await user_service.update_avatar(db, current.user_id, storage_key)
    return _user_out(user, roles)


@router.delete("/me/avatar", response_model=UserOut)
async def delete_my_avatar(
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT, Role.ADMIN, Role.SUB_ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    """Reverts the sidebar back to the default logo."""
    user, roles = await user_service.remove_avatar(db, current.user_id)
    return _user_out(user, roles)


@router.get("/me/avatar")
async def get_my_avatar(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    """The only way to read the current user's own avatar bytes back —
    same authenticated-file pattern as payment proofs
    (app/components/AuthenticatedImage.tsx on the frontend)."""
    user, _roles = await user_service.get_profile(db, current.user_id)
    if user.avatar_key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No profile photo set")
    path = upload_service.resolve_avatar_path(user.avatar_key)
    return FileResponse(path)
