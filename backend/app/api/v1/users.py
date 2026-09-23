"""Self-service profile — every authenticated role edits their own
full_name/email the same way, regardless of dashboard (see
app/services/user_service.py)."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.identity import User
from app.models.enums import Role
from app.schemas.user import ProfileUpdateIn, UserOut
from app.services import user_service

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
