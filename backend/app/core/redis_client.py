"""Shared Redis client — used by OTP service, refresh-token store, rate limits."""
<<<<<<< HEAD
import logging
import time
from typing import Any
import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

from app.core.config import get_settings

logger = logging.getLogger("app.redis")
settings = get_settings()


class InMemoryRedis:
    """Lightweight in-memory fallback for local development when Redis is not installed/running."""
    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._expiries: dict[str, float] = {}

    def _purge_expired(self, key: str) -> None:
        if key in self._expiries and time.time() > self._expiries[key]:
            self._data.pop(key, None)
            self._expiries.pop(key, None)

    async def get(self, name: str) -> str | None:
        self._purge_expired(name)
        return self._data.get(name)

    async def set(
        self,
        name: str,
        value: Any,
        ex: int | None = None,
        px: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        self._purge_expired(name)
        if nx and name in self._data:
            return False
        if xx and name not in self._data:
            return False
        self._data[name] = str(value)
        if ex is not None:
            self._expiries[name] = time.time() + ex
        elif px is not None:
            self._expiries[name] = time.time() + (px / 1000.0)
        else:
            self._expiries.pop(name, None)
        return True

    async def delete(self, *names: str) -> int:
        count = 0
        for name in names:
            if name in self._data:
                self._data.pop(name, None)
                self._expiries.pop(name, None)
                count += 1
        return count

    async def exists(self, *names: str) -> int:
        count = 0
        for name in names:
            self._purge_expired(name)
            if name in self._data:
                count += 1
        return count

    async def incr(self, name: str, amount: int = 1) -> int:
        self._purge_expired(name)
        curr = int(self._data.get(name, 0))
        new_val = curr + amount
        self._data[name] = str(new_val)
        return new_val

    async def expire(self, name: str, time_seconds: int) -> bool:
        self._purge_expired(name)
        if name in self._data:
            self._expiries[name] = time.time() + time_seconds
            return True
        return False

    async def ping(self) -> bool:
        return True

    async def flushdb(self) -> bool:
        self._data.clear()
        self._expiries.clear()
        return True


class ResilientRedisProxy:
    """
    Proxies calls to real Redis. If Redis is unreachable and environment == 'development',
    gracefully falls back to InMemoryRedis so local dev on Windows works without Docker.
    """
    def __init__(self, redis_url: str, is_dev: bool) -> None:
        self._redis_url = redis_url
        self._is_dev = is_dev
        self._real_client = redis.from_url(redis_url, decode_responses=True)
        self._in_memory: InMemoryRedis | None = None
        self._logged_fallback = False

    def _get_fallback(self) -> InMemoryRedis:
        if self._in_memory is None:
            self._in_memory = InMemoryRedis()
        if not self._logged_fallback:
            logger.warning(
                "[DEV MODE] Redis at %s is unreachable. Using in-memory fallback for local development.",
                self._redis_url,
            )
            self._logged_fallback = True
        return self._in_memory

    async def _execute(self, method_name: str, *args, **kwargs):
        if self._in_memory is not None:
            # Already in fallback mode
            method = getattr(self._in_memory, method_name)
            return await method(*args, **kwargs)

        try:
            method = getattr(self._real_client, method_name)
            return await method(*args, **kwargs)
        except (RedisConnectionError, RedisTimeoutError, OSError) as exc:
            if self._is_dev:
                fallback = self._get_fallback()
                method = getattr(fallback, method_name)
                return await method(*args, **kwargs)
            raise

    async def get(self, *args, **kwargs):
        return await self._execute("get", *args, **kwargs)

    async def set(self, *args, **kwargs):
        return await self._execute("set", *args, **kwargs)

    async def delete(self, *args, **kwargs):
        return await self._execute("delete", *args, **kwargs)

    async def exists(self, *args, **kwargs):
        return await self._execute("exists", *args, **kwargs)

    async def incr(self, *args, **kwargs):
        return await self._execute("incr", *args, **kwargs)

    async def expire(self, *args, **kwargs):
        return await self._execute("expire", *args, **kwargs)

    async def ping(self, *args, **kwargs):
        return await self._execute("ping", *args, **kwargs)

    async def flushdb(self, *args, **kwargs):
        return await self._execute("flushdb", *args, **kwargs)


_redis: Any = None


def get_redis() -> Any:
    global _redis
    if _redis is None:
        is_dev = settings.environment == "development"
        _redis = ResilientRedisProxy(settings.redis_url, is_dev=is_dev)
=======
import redis.asyncio as redis

from app.core.config import get_settings

settings = get_settings()
_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
>>>>>>> 191853d0b99367296d07aeb3fd7615459bc0b889
    return _redis
