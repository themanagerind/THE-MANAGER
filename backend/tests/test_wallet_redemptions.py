"""Resident -> Platform Owner Master Wallet point transfer (user-
requested): wallet_service.transfer_to_master_wallet / verify_and_redeem_code,
and the API endpoints around them. The Master Wallet is the Platform
Owner's own existing Wallet row, not a separate system (see
wallet_service.get_master_wallet).

Note: this test DB is session-scoped with no per-test rollback (see
tests/conftest.py), and other test files also seed Platform Owner
accounts for unrelated purposes — get_master_wallet deterministically
converges on the earliest-created one regardless, so these tests always
resolve "the master wallet" via get_master_wallet itself rather than
assuming it's whichever Platform Owner a given test happens to seed."""
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, UserStatus
from app.models.identity import User, UserRole
from app.services import wallet_service
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_resident(db_session: AsyncSession, society_id, mobile: str) -> User:
    resident = User(society_id=society_id, full_name="Redemption Resident", mobile=mobile, status=UserStatus.ACTIVE)
    db_session.add(resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    await db_session.refresh(resident)
    return resident


async def _ensure_a_platform_owner_exists(db_session: AsyncSession, mobile: str) -> None:
    """get_master_wallet needs at least one — doesn't matter which, since
    every assertion below reads back whichever one it actually resolves
    to rather than assuming it's this specific seed."""
    owner = User(society_id=None, full_name="Platform Owner", mobile=mobile, status=UserStatus.ACTIVE)
    db_session.add(owner)
    await db_session.flush()
    db_session.add(UserRole(user_id=owner.id, role=Role.PLATFORM_OWNER, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()


async def test_transfer_debits_resident_credits_master_and_returns_code(
    db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    resident = await _seed_resident(db_session, society_id, "9860000001")
    await _ensure_a_platform_owner_exists(db_session, "9860000099")

    await wallet_service.credit_maintenance_payment(db_session, resident.id, None, 1000.0)
    await db_session.commit()

    master_before = await wallet_service.get_master_wallet(db_session)
    balance_before = float(master_before.balance)

    redemption = await wallet_service.transfer_to_master_wallet(db_session, resident.id, 400.0)

    assert len(redemption.code) == 8
    assert float(redemption.amount) == 400.0
    assert redemption.is_used is False

    resident_wallet = await wallet_service.get_wallet(db_session, resident.id)
    assert float(resident_wallet.balance) == 600.0

    master_after = await wallet_service.get_master_wallet(db_session)
    assert float(master_after.balance) == balance_before + 400.0


async def test_transfer_rejects_insufficient_balance(db_session: AsyncSession, two_societies_with_admins):
    society_id = two_societies_with_admins["a"]["society_id"]
    resident = await _seed_resident(db_session, society_id, "9860000002")
    await _ensure_a_platform_owner_exists(db_session, "9860000098")

    await wallet_service.credit_maintenance_payment(db_session, resident.id, None, 100.0)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await wallet_service.transfer_to_master_wallet(db_session, resident.id, 500.0)
    assert exc.value.status_code == 409

    # Rejected before any wallet was touched — resident balance untouched.
    resident_wallet = await wallet_service.get_wallet(db_session, resident.id)
    assert float(resident_wallet.balance) == 100.0


async def test_verify_and_redeem_code_marks_used_once(db_session: AsyncSession, two_societies_with_admins):
    society_id = two_societies_with_admins["a"]["society_id"]
    resident = await _seed_resident(db_session, society_id, "9860000003")
    await _ensure_a_platform_owner_exists(db_session, "9860000097")

    await wallet_service.credit_maintenance_payment(db_session, resident.id, None, 1000.0)
    await db_session.commit()
    redemption = await wallet_service.transfer_to_master_wallet(db_session, resident.id, 250.0)

    verified = await wallet_service.verify_and_redeem_code(db_session, redemption.code)
    assert float(verified.amount) == 250.0
    assert verified.is_used is True
    assert verified.used_at is not None

    with pytest.raises(HTTPException) as exc:
        await wallet_service.verify_and_redeem_code(db_session, redemption.code)
    assert exc.value.status_code == 409


async def test_verify_unknown_code_404(db_session: AsyncSession, two_societies_with_admins):
    with pytest.raises(HTTPException) as exc:
        await wallet_service.verify_and_redeem_code(db_session, "NOTAREAL")
    assert exc.value.status_code == 404


# --- API endpoints -----------------------------------------------------------


async def test_resident_can_create_and_list_redemptions_via_api(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    resident = await _seed_resident(db_session, society_id, "9860000004")
    await _ensure_a_platform_owner_exists(db_session, "9860000096")

    await wallet_service.credit_maintenance_payment(db_session, resident.id, None, 1000.0)
    await db_session.commit()

    headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.post("/api/v1/wallet-redemptions", json={"amount": 300.0}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["amount"] == 300.0
    assert len(body["code"]) == 8

    resp = await client.get("/api/v1/wallet-redemptions/mine", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(i["code"] == body["code"] for i in items)


async def test_non_resident_cannot_create_redemption(
    client: AsyncClient, two_societies_with_admins
):
    admin_id = two_societies_with_admins["a"]["admin_id"]
    society_id = two_societies_with_admins["a"]["society_id"]
    headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post("/api/v1/wallet-redemptions", json={"amount": 100.0}, headers=headers)
    assert resp.status_code == 403


async def test_verify_endpoint_requires_store_api_key(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    resident = await _seed_resident(db_session, society_id, "9860000005")
    await _ensure_a_platform_owner_exists(db_session, "9860000095")
    await wallet_service.credit_maintenance_payment(db_session, resident.id, None, 1000.0)
    await db_session.commit()
    redemption = await wallet_service.transfer_to_master_wallet(db_session, resident.id, 150.0)

    # No key at all.
    resp = await client.post("/api/v1/wallet-redemptions/verify", json={"code": redemption.code})
    assert resp.status_code == 401

    # Wrong key.
    resp = await client.post(
        "/api/v1/wallet-redemptions/verify", json={"code": redemption.code},
        headers={"X-Store-Api-Key": "totally-wrong"},
    )
    assert resp.status_code == 401

    # Correct key (matches ECOM_STORE_API_KEY seeded in conftest).
    resp = await client.post(
        "/api/v1/wallet-redemptions/verify", json={"code": redemption.code},
        headers={"X-Store-Api-Key": "test-store-api-key-for-pytest-only"},
    )
    assert resp.status_code == 200
    assert resp.json()["amount"] == 150.0

    # Second verify of the same code is a clean 409, not a 500.
    resp = await client.post(
        "/api/v1/wallet-redemptions/verify", json={"code": redemption.code},
        headers={"X-Store-Api-Key": "test-store-api-key-for-pytest-only"},
    )
    assert resp.status_code == 409
