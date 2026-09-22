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
