"""
OTP generation/verification — hardened per production security checklist:
  - OTP is HASHED in Redis, never stored/logged in plaintext
  - Request rate limit: min 60s between requests, max 5 requests/hour/mobile
  - Verify attempt lockout: max 5 wrong attempts -> mobile locked for 15 min
    (and the OTP itself is invalidated, forcing a fresh request)
"""
import hashlib
import hmac
import secrets
import string

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.redis_client import get_redis

settings = get_settings()

_MAX_REQUESTS_PER_HOUR = 5
_MIN_SECONDS_BETWEEN_REQUESTS = 60
_MAX_VERIFY_ATTEMPTS = 5
_LOCKOUT_SECONDS = 15 * 60


def _otp_key(mobile: str) -> str:
    return f"otp:value:{mobile}"


def _cooldown_key(mobile: str) -> str:
    return f"otp:cooldown:{mobile}"


def _rate_key(mobile: str) -> str:
    return f"otp:rate:{mobile}"


def _attempts_key(mobile: str) -> str:
    return f"otp:attempts:{mobile}"


def _lockout_key(mobile: str) -> str:
    return f"otp:lockout:{mobile}"


def _hash_otp(mobile: str, otp: str) -> str:
    # HMAC keyed by the app secret — an attacker with read access to Redis
    # alone still can't recover the OTP or forge a valid hash.
    msg = f"{mobile}:{otp}".encode()
    return hmac.new(settings.jwt_secret_key.encode(), msg, hashlib.sha256).hexdigest()


def _generate_otp() -> str:
    # Audit fix: random.choices() is not cryptographically secure — an OTP
    # is an auth credential, so it needs a CSPRNG (secrets module) the same
    # way a password reset token would.
    return "".join(secrets.choice(string.digits) for _ in range(settings.otp_length))


async def request_otp(mobile: str) -> str:
    r = get_redis()

    if await r.exists(_lockout_key(mobile)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed attempts — try again later",
        )
    if await r.exists(_cooldown_key(mobile)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Please wait before requesting another OTP",
        )

    request_count = await r.incr(_rate_key(mobile))
    if request_count == 1:
        await r.expire(_rate_key(mobile), 3600)
    if request_count > _MAX_REQUESTS_PER_HOUR:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many OTP requests for this number — try again in an hour",
        )

    otp = _generate_otp()
    await r.set(_otp_key(mobile), _hash_otp(mobile, otp), ex=settings.otp_expiry_seconds)
    await r.set(_cooldown_key(mobile), "1", ex=_MIN_SECONDS_BETWEEN_REQUESTS)
    await r.delete(_attempts_key(mobile))  # fresh OTP resets the attempt counter
    return otp  # caller dispatches via SMS gateway — never logged/returned to the client


async def verify_otp(mobile: str, otp: str) -> bool:
    r = get_redis()

    if await r.exists(_lockout_key(mobile)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts — try again later"
        )

    stored_hash = await r.get(_otp_key(mobile))
    if stored_hash is None:
        return False  # expired or never requested

    if not hmac.compare_digest(stored_hash, _hash_otp(mobile, otp)):
        attempts = await r.incr(_attempts_key(mobile))
        if attempts == 1:
            await r.expire(_attempts_key(mobile), settings.otp_expiry_seconds)
        if attempts >= _MAX_VERIFY_ATTEMPTS:
            await r.set(_lockout_key(mobile), "1", ex=_LOCKOUT_SECONDS)
            await r.delete(_otp_key(mobile), _attempts_key(mobile))
        return False

    await r.delete(_otp_key(mobile), _attempts_key(mobile))  # one-time use
    return True
