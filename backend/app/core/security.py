"""
JWT issuance/verification and the get_current_user / require_role FastAPI
dependencies.

Section 49.14 / Section 27 (non-negotiable): JWT `active_role` is a context
HINT only. Every protected endpoint re-verifies against current DB state
(user_roles / sub_admin_scopes) via the dependencies here — never trust the
token's claims alone for authorization decisions.
"""
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.redis_client import get_redis
from app.models.enums import Role, SocietyStatus, UserStatus
from app.models.identity import Society, User, UserRole

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
    session_started_at: datetime,
) -> str:
    """`session_started_at` is the ORIGINAL login time for this session
    chain — callers must carry it forward unchanged on every refresh/role-
    switch (never reset it), since auth_service.rotate_refresh_token's
    12-hour absolute cap for privileged roles measures from this, not from
    whenever the access token itself happened to be (re)issued. Only a
    fresh OTP-verified login sets it to "now".

    `jti` (new, user-reported gap) lets logout blocklist THIS specific
    access token for its remaining lifetime — see revoke_access_token.
    Previously logout only revoked the refresh token, leaving an already-
    issued access token usable for up to its remaining ~30 minutes."""
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
        "jti": str(uuid.uuid4()),
        "session_started_at": session_started_at.isoformat(),
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
    they were in when the token was issued; roles/scope are re-checked here.

    access_jti/access_exp/session_started_at are decoded straight from the
    access token's own claims (never re-derived) — access_jti/access_exp
    back the logout blocklist (revoke_access_token), session_started_at
    backs the 12-hour absolute session cap for privileged roles
    (auth_service.rotate_refresh_token/switch_role)."""

    model_config = {"arbitrary_types_allowed": True}

    user_id: uuid.UUID
    society_id: uuid.UUID | None
    active_role: Role
    available_roles: list[Role]
    access_jti: str
    access_exp: datetime
    session_started_at: datetime


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not an access token")

    access_jti = payload.get("jti")
    if access_jti is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed access token")
    if await is_access_token_revoked(access_jti):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has been revoked — please log in again")

    user_id = uuid.UUID(payload["sub"])

    # Re-derive current state from DB — the whole point of Section 49.14.
    # Joined so a society suspended AFTER token issuance is caught on every
    # subsequent request, not just at login — an existing JWT alone must
    # never keep working once the society is suspended.
    row = (
        await db.execute(
            select(User, Society.status)
            .outerjoin(Society, User.society_id == Society.id)
            .where(User.id == user_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or not active")
    user, society_status = row
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or not active")
    if user.society_id is not None and society_status != SocietyStatus.ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Society is suspended")

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
        access_jti=access_jti,
        access_exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        session_started_at=datetime.fromisoformat(payload["session_started_at"]),
    )


def _access_blocklist_key(jti: str) -> str:
    return f"revoked_access_jti:{jti}"


async def revoke_access_token(jti: str, ttl_seconds: int) -> None:
    """Blocklists this specific access token so it's rejected on its very
    next use (get_current_user, above), even though it remains
    cryptographically valid (signature + exp) until its own natural expiry
    — logout revoking only the refresh token left an already-issued access
    token usable for up to its remaining ~30 minutes (user-reported gap).
    ttl_seconds should be the token's own remaining lifetime; the
    blocklist entry expires alongside it so this never grows unbounded."""
    if ttl_seconds <= 0:
        return  # already expired on its own — nothing to blocklist
    r = get_redis()
    await r.set(_access_blocklist_key(jti), "1", ex=ttl_seconds)


async def is_access_token_revoked(jti: str) -> bool:
    r = get_redis()
    return bool(await r.exists(_access_blocklist_key(jti)))


_store_api_key_header = APIKeyHeader(name="X-Store-Api-Key", auto_error=False)


async def require_store_api_key(
    provided: Annotated[str | None, Depends(_store_api_key_header)],
) -> None:
    """Service-to-service auth for the (future, separate) Ecom store's
    backend — never a Resident's own JWT, since the caller is the
    store's server, not a logged-in person. No Bearer token, no DB
    lookup: a single shared secret, same trust model as a webhook. If
    the operator hasn't set ECOM_STORE_API_KEY yet, the endpoint is
    unreachable (503) rather than silently accepting anything.
    hmac.compare_digest, not `!=` — same reasoning as otp_service's own
    constant-time check, so repeated guesses can't time their way to the
    key one byte at a time."""
    configured = settings.ecom_store_api_key
    if not configured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Ecom store integration is not configured")
    if not provided or not hmac.compare_digest(provided, configured):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing store API key")


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
