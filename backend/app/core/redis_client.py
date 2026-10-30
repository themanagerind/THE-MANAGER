"""Shared Redis client — used by OTP service, refresh-token store, rate limits."""
import redis.asyncio as redis

from app.core.config import get_settings

settings = get_settings()
_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis
