"""
Refresh token store — Redis-backed, per Master Rule's "should-fix" list:
rotation (old token invalidated on every refresh) + revocation (logout,
or forced sign-out of a compromised session).

Each refresh token carries a unique `jti`. A valid jti is a Redis key
`refresh_jti:{user_id}:{jti}` with a TTL matching the token's lifetime.
Refreshing deletes the old jti and creates a new one (rotation) — reusing
an already-rotated (or logged-out) refresh token fails immediately, which
is the standard signal of token theft/replay.

The key's VALUE is the session's original login time (ISO 8601), not a
placeholder — carried forward unchanged across every rotation (never
reset here) so auth_service.rotate_refresh_token can enforce the 12-hour
absolute session cap for privileged roles by measuring from the real
login, not from whenever the token was last refreshed (user-requested).
"""
import uuid
from datetime import datetime

from app.core.config import get_settings
from app.core.redis_client import get_redis

settings = get_settings()


def _jti_key(user_id: uuid.UUID, jti: str) -> str:
    return f"refresh_jti:{user_id}:{jti}"


async def issue_jti(user_id: uuid.UUID, session_started_at: datetime) -> str:
    jti = str(uuid.uuid4())
    r = get_redis()
    await r.set(
        _jti_key(user_id, jti), session_started_at.isoformat(),
        ex=settings.jwt_refresh_token_expire_days * 86400,
    )
    return jti


async def consume_jti(user_id: uuid.UUID, jti: str) -> datetime | None:
    """Atomic check-and-revoke (fix, audit round-8 item 8): the previous
    is_jti_valid() -> revoke_jti() two-step had a race window where two
    concurrent refresh calls with the same (stolen or double-submitted)
    token could both pass the check before either deleted the key. GETDEL
    is a single atomic Redis command — only the first caller ever gets a
    non-None result; every subsequent caller (even microseconds later)
    sees the key already gone.

    Returns the session's original login time (this jti's stored value)
    on success — None if the jti was invalid, already used, or revoked."""
    r = get_redis()
    value = await r.getdel(_jti_key(user_id, jti))
    if value is None:
        return None
    return datetime.fromisoformat(value)


async def is_jti_valid(user_id: uuid.UUID, jti: str) -> bool:
    r = get_redis()
    return bool(await r.exists(_jti_key(user_id, jti)))


async def revoke_jti(user_id: uuid.UUID, jti: str) -> None:
    r = get_redis()
    await r.delete(_jti_key(user_id, jti))


async def revoke_all_for_user(user_id: uuid.UUID) -> None:
    """Force-logout every session for this user (e.g. on suspicious activity,
    or when an Admin/Sub-admin role is revoked)."""
    r = get_redis()
    pattern = f"refresh_jti:{user_id}:*"
    async for key in r.scan_iter(match=pattern):
        await r.delete(key)
