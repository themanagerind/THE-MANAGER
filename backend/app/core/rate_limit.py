"""
Shared Redis-backed rate limiter — the incr/expire/429 pattern was
duplicated across otp_service, resident_service (signup), society_service
(search), and upload_service before this; factored out here so new
call sites (payments, account entries, sub-admin permission changes —
CLAUDE.md's own list of actions that need this) don't duplicate it a
fifth and sixth time.
"""
from fastapi import HTTPException, status

from app.core.redis_client import get_redis


async def enforce_rate_limit(key: str, max_attempts: int, window_seconds: int, message: str) -> None:
    """Raises 429 once `key` has been hit more than `max_attempts` times
    within `window_seconds`. The window starts on the first hit (not a
    fixed clock boundary), same as every existing caller of this pattern."""
    r = get_redis()
    attempts = await r.incr(key)
    if attempts == 1:
        await r.expire(key, window_seconds)
    if attempts > max_attempts:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, message)
