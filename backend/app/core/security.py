"""
JWT issuance/verification and the get_current_user / require_role FastAPI
dependencies.

Section 49.14 / Section 27 (non-negotiable): JWT `active_role` is a context
HINT only. Every protected endpoint re-verifies against current DB state
(user_roles / sub_admin_scopes) via the dependencies here — never trust the
token's claims alone for authorization decisions.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.models.enums import Role, UserStatus
from app.models.identity import User, UserRole

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    sub: str  # user_id
    society_id: str | None
    active_role: str
    available_roles: list[str]
    exp: datetime


def create_access_token(
    user_id: uuid.UUID,
    society_id: uuid.UUID | None,
    active_role: Role,
    available_roles: list[Role],
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "society_id": str(society_id) if society_id else None,
        "active_role": active_role.value,
        "available_roles": [r.value for r in available_roles],
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID, jti: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {"sub": str(user_id), "jti": jti, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_otp_session_token(mobile: str) -> str:
    """Short-lived proof that OTP was verified for `mobile`, used only to
    disambiguate which account to log into when one mobile matches multiple
    users (Section 2.1) — not a general-purpose access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload = {"mobile": mobile, "exp": expire, "type": "otp_session"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_otp_session_token(token: str) -> str:
    """Returns the verified mobile number, or raises 401."""
    payload = decode_token(token)
    if payload.get("type") != "otp_session":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid OTP session token")
    return payload["mobile"]


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc


class CurrentUser(BaseModel):
    """Re-derived from the DB on every request — NOT trusted from the JWT
    alone (Section 49.14). The JWT only tells us *which* user + which mode
    they were in when the token was issued; roles/scope are re-checked here."""

    model_config = {"arbitrary_types_allowed": True}

    user_id: uuid.UUID
    society_id: uuid.UUID | None
    active_role: Role
    available_roles: list[Role]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not an access token")

    user_id = uuid.UUID(payload["sub"])

    # Re-derive current state from DB — the whole point of Section 49.14.
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or not active")

    active_roles_rows = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.revoked_at.is_(None))
        )
    ).scalars().all()
    available_roles = [Role(r.role) for r in active_roles_rows]

    requested_active_role = Role(payload["active_role"])
    if requested_active_role not in available_roles:
        # The role this token claims as active has been revoked since issuance —
        # exactly the stale-JWT scenario Section 49.14 requires us to catch.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Active role no longer valid — please re-authenticate or switch role",
        )

    return CurrentUser(
        user_id=user_id,
        society_id=user.society_id,
        active_role=requested_active_role,
        available_roles=available_roles,
    )


def require_role(*allowed: Role):
    """Dependency factory: require_role(Role.ADMIN, Role.SUB_ADMIN)."""

    async def _check(current: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if current.active_role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Requires one of: {[r.value for r in allowed]}, got {current.active_role.value}",
            )
        return current

    return _check
