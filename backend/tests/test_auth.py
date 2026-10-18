"""Login/role tests — priority #1 per Section 42 testing priorities."""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.models.enums import Role, UserStatus
from app.models.identity import User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _create_active_user(db_session: AsyncSession, society_id, mobile: str, roles: list[Role]) -> User:
    user = User(society_id=society_id, full_name="Test User", mobile=mobile, status=UserStatus.ACTIVE)
    db_session.add(user)
    await db_session.flush()
    for role in roles:
        db_session.add(UserRole(user_id=user.id, role=role, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_otp_request_and_verify_issues_tokens(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins, monkeypatch
):
    mobile = "9000000099"
    society_id = two_societies_with_admins["a"]["society_id"]
    await _create_active_user(db_session, society_id, mobile, [Role.RESIDENT])

    # request_otp() never returns the plaintext to the HTTP caller (by design —
    # it's dispatched via SMS in production), so pin the generator to a known
    # value instead of requesting a second OTP, which would just hit the same
    # 60s cooldown this endpoint call sets.
    from app.services import otp_service
    monkeypatch.setattr(otp_service, "_generate_otp", lambda: "123456")

    resp = await client.post("/api/v1/auth/otp/request", json={"mobile": mobile})
    assert resp.status_code == 200

    r = get_redis()
    stored_hash = await r.get(f"otp:value:{mobile}")
    assert stored_hash is not None  # OTP exists but is hashed, never returned to caller

    resp = await client.post("/api/v1/auth/otp/verify", json={"mobile": mobile, "otp": "123456"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tokens"] is not None
    assert body["tokens"]["active_role"] == "RESIDENT"


async def test_otp_verify_wrong_code_fails(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    mobile = "9000000098"
    society_id = two_societies_with_admins["a"]["society_id"]
    await _create_active_user(db_session, society_id, mobile, [Role.RESIDENT])

    from app.services.otp_service import request_otp as _req
    await _req(mobile)

    resp = await client.post("/api/v1/auth/otp/verify", json={"mobile": mobile, "otp": "000000"})
    assert resp.status_code == 401


async def test_otp_lockout_after_max_attempts(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    mobile = "9000000097"
    society_id = two_societies_with_admins["a"]["society_id"]
    await _create_active_user(db_session, society_id, mobile, [Role.RESIDENT])

    from app.services.otp_service import request_otp as _req
    await _req(mobile)

    for _ in range(5):
        await client.post("/api/v1/auth/otp/verify", json={"mobile": mobile, "otp": "000000"})

    resp = await client.post("/api/v1/auth/otp/request", json={"mobile": mobile})
    assert resp.status_code == 429


async def test_otp_request_rate_limited(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    mobile = "9000000096"
    society_id = two_societies_with_admins["a"]["society_id"]
    await _create_active_user(db_session, society_id, mobile, [Role.RESIDENT])

    resp1 = await client.post("/api/v1/auth/otp/request", json={"mobile": mobile})
    assert resp1.status_code == 200
    resp2 = await client.post("/api/v1/auth/otp/request", json={"mobile": mobile})
    assert resp2.status_code == 429


async def test_dual_role_switch_admin_to_resident(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    society_id = two_societies_with_admins["a"]["society_id"]
    user = await _create_active_user(db_session, society_id, "9000000095", [Role.ADMIN, Role.RESIDENT])

    headers = auth_headers(user.id, society_id, Role.ADMIN, [Role.ADMIN, Role.RESIDENT])
    resp = await client.post("/api/v1/auth/switch-role", json={"active_role": "RESIDENT"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["active_role"] == "RESIDENT"


async def test_switch_to_unavailable_role_rejected(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    society_id = two_societies_with_admins["a"]["society_id"]
    user = await _create_active_user(db_session, society_id, "9000000094", [Role.RESIDENT])

    headers = auth_headers(user.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.post("/api/v1/auth/switch-role", json={"active_role": "ADMIN"}, headers=headers)
    assert resp.status_code == 403


async def test_stale_jwt_after_role_revoked_is_rejected(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    """Section 49.14 — JWT active_role is a hint only; a token claiming a
    since-revoked role must be rejected, not trusted."""
    society_id = two_societies_with_admins["a"]["society_id"]
    user = await _create_active_user(db_session, society_id, "9000000093", [Role.SUB_ADMIN])

    headers = auth_headers(user.id, society_id, Role.SUB_ADMIN, [Role.SUB_ADMIN])

    from sqlalchemy import update
    await db_session.execute(
        update(UserRole).where(UserRole.user_id == user.id).values(revoked_at=datetime.now(timezone.utc))
    )
    await db_session.commit()

    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401


async def test_otp_request_dispatches_via_sms_gateway(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins, monkeypatch
):
    """Regression test: request_otp_endpoint used to discard the generated
    OTP entirely (no SMS integration was wired up), so no one could ever
    actually receive it. Now it's dispatched through sms_service (currently
    a mock — see app/services/sms_service.py) — confirm the endpoint calls
    it with the right mobile and the same OTP that got hashed into Redis."""
    mobile = "9000000097"
    society_id = two_societies_with_admins["a"]["society_id"]
    await _create_active_user(db_session, society_id, mobile, [Role.RESIDENT])

    from app.services import otp_service
    monkeypatch.setattr(otp_service, "_generate_otp", lambda: "654321")

    dispatched = []

    async def fake_send(mobile_arg, otp_arg):
        dispatched.append((mobile_arg, otp_arg))

    # auth.py imported send_otp_sms by name, so patching the reference it
    # actually holds (not the sms_service module attribute) is what matters.
    import app.api.v1.auth as auth_module
    monkeypatch.setattr(auth_module, "send_otp_sms", fake_send)

    resp = await client.post("/api/v1/auth/otp/request", json={"mobile": mobile})
    assert resp.status_code == 200

    assert dispatched == [(mobile, "654321")]


# --- Logout access-token blocklist (user-reported gap) -----------------------
# bearer_token_for/auth_headers don't touch Redis (no refresh-token jti
# issued), so these call auth_service.issue_tokens_for directly to get a
# token pair that's actually wired through Redis like a real login.


async def test_logout_blocklists_the_access_token_that_authenticated_it(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    from app.services import auth_service

    society_id = two_societies_with_admins["a"]["society_id"]
    user = await _create_active_user(db_session, society_id, "9000000092", [Role.RESIDENT])
    tokens = await auth_service.issue_tokens_for(db_session, user)
    headers = {"Authorization": f"Bearer {tokens.access_token}"}

    # Works before logout.
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200

    resp = await client.post("/api/v1/auth/logout", json={"refresh_token": tokens.refresh_token}, headers=headers)
    assert resp.status_code == 200

    # The SAME access token — still cryptographically valid (signature +
    # exp not yet reached) — is rejected immediately, not just after its
    # own ~30-minute expiry. This is the gap the blocklist closes.
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401


async def test_logout_does_not_affect_a_different_devices_session(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Logout scope is per-session (the device that called it), not
    per-account — a second, independently-issued token pair for the same
    user must keep working."""
    from app.services import auth_service

    society_id = two_societies_with_admins["a"]["society_id"]
    user = await _create_active_user(db_session, society_id, "9000000091", [Role.RESIDENT])
    device_a = await auth_service.issue_tokens_for(db_session, user)
    device_b = await auth_service.issue_tokens_for(db_session, user)

    headers_a = {"Authorization": f"Bearer {device_a.access_token}"}
    headers_b = {"Authorization": f"Bearer {device_b.access_token}"}

    await client.post("/api/v1/auth/logout", json={"refresh_token": device_a.refresh_token}, headers=headers_a)

    assert (await client.get("/api/v1/auth/me", headers=headers_a)).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers=headers_b)).status_code == 200


# --- 12-hour absolute session cap for privileged roles (user-requested) ------
# Platform Owner only for now — Admin/Sub-admin were disabled from this set
# (user-requested, after briefly including them — see git history), so they
# behave like Manager/Guard/Resident: no cap.


async def test_refresh_rejected_after_12_hours_for_platform_owner(
    db_session: AsyncSession, two_societies_with_admins
):
    from datetime import datetime, timedelta, timezone

    from fastapi import HTTPException

    from app.services import auth_service, token_service

    user = await _create_active_user(db_session, None, "9000000090", [Role.PLATFORM_OWNER])

    old_login = datetime.now(timezone.utc) - timedelta(hours=12, minutes=1)
    old_jti = await token_service.issue_jti(user.id, old_login)

    with pytest.raises(HTTPException) as exc:
        await auth_service.rotate_refresh_token(db_session, user.id, old_jti)
    assert exc.value.status_code == 401


async def test_refresh_still_works_just_under_12_hours_for_platform_owner(
    db_session: AsyncSession, two_societies_with_admins
):
    from datetime import datetime, timedelta, timezone

    from app.services import auth_service, token_service

    user = await _create_active_user(db_session, None, "9000000089", [Role.PLATFORM_OWNER])

    recent_login = datetime.now(timezone.utc) - timedelta(hours=11, minutes=59)
    jti = await token_service.issue_jti(user.id, recent_login)

    tokens = await auth_service.rotate_refresh_token(db_session, user.id, jti)
    assert tokens.access_token


async def test_refresh_has_no_12_hour_cap_for_resident(
    db_session: AsyncSession, two_societies_with_admins
):
    """Only Platform Owner carries the cap (user-requested scope) — a
    plain Resident session of any age keeps refreshing."""
    from datetime import datetime, timedelta, timezone

    from app.services import auth_service, token_service

    society_id = two_societies_with_admins["a"]["society_id"]
    user = await _create_active_user(db_session, society_id, "9000000088", [Role.RESIDENT])

    ancient_login = datetime.now(timezone.utc) - timedelta(days=5)
    jti = await token_service.issue_jti(user.id, ancient_login)

    tokens = await auth_service.rotate_refresh_token(db_session, user.id, jti)
    assert tokens.access_token


async def test_refresh_has_no_12_hour_cap_for_admin(
    db_session: AsyncSession, two_societies_with_admins
):
    """Admin was deliberately disabled from the capped-roles set
    (user-requested) — an old session still refreshes freely."""
    from datetime import datetime, timedelta, timezone

    from app.services import auth_service, token_service

    society_id = two_societies_with_admins["a"]["society_id"]
    user = await _create_active_user(db_session, society_id, "9000000091", [Role.ADMIN])

    old_login = datetime.now(timezone.utc) - timedelta(hours=13)
    jti = await token_service.issue_jti(user.id, old_login)

    tokens = await auth_service.rotate_refresh_token(db_session, user.id, jti)
    assert tokens.access_token


async def test_refresh_has_no_12_hour_cap_for_sub_admin_dual_resident(
    db_session: AsyncSession, two_societies_with_admins
):
    """Sub-admin was deliberately disabled from the capped-roles set
    (user-requested) — an old Sub-admin+Resident dual-role session still
    refreshes freely."""
    from datetime import datetime, timedelta, timezone

    from app.services import auth_service, token_service

    society_id = two_societies_with_admins["a"]["society_id"]
    user = await _create_active_user(
        db_session, society_id, "9000000087", [Role.SUB_ADMIN, Role.RESIDENT]
    )

    old_login = datetime.now(timezone.utc) - timedelta(hours=13)
    jti = await token_service.issue_jti(user.id, old_login)

    tokens = await auth_service.rotate_refresh_token(db_session, user.id, jti)
    assert tokens.access_token


async def test_switch_role_carries_session_started_at_forward_not_reset(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Switching role must not grant a fresh 12-hour window — otherwise an
    Admin could dodge the cap indefinitely by switching roles periodically.
    Checked by decoding the new access token's own session_started_at
    claim (deterministic) rather than racing wall-clock timing against a
    second rotate_refresh_token call."""
    from datetime import datetime, timedelta, timezone

    from app.services import auth_service, token_service

    society_id = two_societies_with_admins["a"]["society_id"]
    user = await _create_active_user(
        db_session, society_id, "9000000086", [Role.ADMIN, Role.RESIDENT]
    )

    old_login = datetime.now(timezone.utc) - timedelta(hours=11, minutes=55)
    jti = await token_service.issue_jti(user.id, old_login)
    tokens = await auth_service.rotate_refresh_token(db_session, user.id, jti)

    headers = {"Authorization": f"Bearer {tokens.access_token}"}
    resp = await client.post("/api/v1/auth/switch-role", json={"active_role": "RESIDENT"}, headers=headers)
    assert resp.status_code == 200

    from app.core.security import decode_token
    switched_payload = decode_token(resp.json()["access_token"])
    switched_started = datetime.fromisoformat(switched_payload["session_started_at"])
    assert abs((switched_started - old_login).total_seconds()) < 1


# --- Audit fixes ---------------------------------------------------------


async def test_switch_role_itself_enforces_12_hour_cap_for_platform_owner(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Audit finding: switch_role carried session_started_at forward but
    never checked the cap itself, so repeated switch-role calls (even back
    to the same role) could mint fresh token pairs forever without ever
    going through /token/refresh, silently bypassing the 12-hour cap."""
    from datetime import datetime, timedelta, timezone

    from app.services import auth_service

    user = await _create_active_user(db_session, None, "9000000084", [Role.PLATFORM_OWNER])

    old_login = datetime.now(timezone.utc) - timedelta(hours=12, minutes=1)
    tokens = await auth_service.issue_tokens_for(db_session, user, session_started_at=old_login)

    headers = {"Authorization": f"Bearer {tokens.access_token}"}
    resp = await client.post(
        "/api/v1/auth/switch-role", json={"active_role": "PLATFORM_OWNER"}, headers=headers
    )
    assert resp.status_code == 401


async def test_consume_jti_handles_pre_migration_placeholder_value_without_crashing(
    db_session: AsyncSession, two_societies_with_admins
):
    """Audit finding: refresh tokens issued before session_started_at
    existed as this Redis value stored the old placeholder "1", which
    datetime.fromisoformat can't parse. consume_jti must fall back
    gracefully (not raise), since the key is already GETDEL'd by the time
    the parse is attempted — there's no way to retry a crash here."""
    import uuid

    from app.core.redis_client import get_redis
    from app.services import token_service

    user_id = uuid.uuid4()
    jti = str(uuid.uuid4())
    r = get_redis()
    await r.set(f"refresh_jti:{user_id}:{jti}", "1", ex=60)  # pre-migration placeholder shape

    result = await token_service.consume_jti(user_id, jti)
    assert result is not None  # didn't raise, and didn't treat it as "invalid token" either


async def test_me_endpoint_does_not_leak_internal_token_fields(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Audit finding: GET /auth/me used to return the internal CurrentUser
    object directly, which (after this PR) carries access_jti/access_exp/
    session_started_at — token-identifying and session-age metadata with
    no business in a response body."""
    society_id = two_societies_with_admins["a"]["society_id"]
    user = await _create_active_user(db_session, society_id, "9000000083", [Role.RESIDENT])
    headers = auth_headers(user.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"user_id", "society_id", "active_role", "available_roles"}


async def test_fresh_login_starts_a_new_session_clock(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins, monkeypatch
):
    """A brand-new OTP login must NOT inherit any prior session's age —
    confirms issue_tokens_for defaults session_started_at to now when none
    is passed in."""
    from datetime import datetime, timedelta, timezone

    mobile = "9000000085"
    society_id = two_societies_with_admins["a"]["society_id"]
    await _create_active_user(db_session, society_id, mobile, [Role.ADMIN])

    from app.services import otp_service
    monkeypatch.setattr(otp_service, "_generate_otp", lambda: "111222")

    await client.post("/api/v1/auth/otp/request", json={"mobile": mobile})
    resp = await client.post("/api/v1/auth/otp/verify", json={"mobile": mobile, "otp": "111222"})
    access_token = resp.json()["tokens"]["access_token"]

    from app.core.security import decode_token
    payload = decode_token(access_token)
    started = datetime.fromisoformat(payload["session_started_at"])
    assert datetime.now(timezone.utc) - started < timedelta(seconds=10)
