"""Wallet redemption — "activating" the resident wallet for spending, not
just earning (user-requested). Credit behavior (credit_maintenance_payment)
is explicitly unchanged — these tests cover only the new debit primitive,
redeem_points, which nothing in the product calls yet (a future Ecom PWA
discount redemption will)."""
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, UserStatus, WalletTxnType
from app.models.identity import User, UserRole
from app.services import wallet_service

pytestmark = pytest.mark.asyncio


async def _seed_resident(db_session: AsyncSession, society_id, mobile: str) -> User:
    resident = User(society_id=society_id, full_name="Wallet Resident", mobile=mobile, status=UserStatus.ACTIVE)
    db_session.add(resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    await db_session.refresh(resident)
    return resident


async def test_redeem_points_debits_balance_and_records_transaction(
    db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    resident = await _seed_resident(db_session, society_id, "9850000001")

    await wallet_service.credit_maintenance_payment(db_session, resident.id, None, 1000.0)
    await db_session.commit()

    txn = await wallet_service.redeem_points(
        db_session, resident.id, 300.0, "10% off at the Ecom store", created_by=resident.id
    )
    await db_session.commit()

    assert txn.transaction_type == WalletTxnType.REDEMPTION
    assert float(txn.amount) == -300.0

    wallet = await wallet_service.get_wallet(db_session, resident.id)
    assert float(wallet.balance) == 700.0


async def test_redeem_points_rejects_insufficient_balance(
    db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    resident = await _seed_resident(db_session, society_id, "9850000002")

    await wallet_service.credit_maintenance_payment(db_session, resident.id, None, 200.0)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await wallet_service.redeem_points(db_session, resident.id, 500.0, "too much", created_by=resident.id)
    assert exc.value.status_code == 409

    wallet = await wallet_service.get_wallet(db_session, resident.id)
    assert float(wallet.balance) == 200.0  # untouched — rejected, not partially applied


async def test_redeem_points_rejects_non_positive_amount(
    db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    resident = await _seed_resident(db_session, society_id, "9850000003")

    with pytest.raises(HTTPException) as exc:
        await wallet_service.redeem_points(db_session, resident.id, 0.0, "zero", created_by=resident.id)
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        await wallet_service.redeem_points(db_session, resident.id, -50.0, "negative", created_by=resident.id)
    assert exc.value.status_code == 400


async def test_credit_maintenance_payment_unchanged_full_amount_regardless(
    db_session: AsyncSession, two_societies_with_admins
):
    """Explicitly confirmed by the user: the credit formula does not
    change — a payment always credits its full amount, whether it was
    paid on time or late (penalty_amount already folded into the amount
    passed in by the caller, same as before this feature)."""
    society_id = two_societies_with_admins["a"]["society_id"]
    resident = await _seed_resident(db_session, society_id, "9850000004")

    # Simulates a late payment where amount already includes a penalty —
    # credit_maintenance_payment still credits the whole thing, unchanged.
    txn = await wallet_service.credit_maintenance_payment(db_session, resident.id, None, 1250.0)
    await db_session.commit()

    assert txn.transaction_type == WalletTxnType.MAINTENANCE_CREDIT
    assert float(txn.amount) == 1250.0
    wallet = await wallet_service.get_wallet(db_session, resident.id)
    assert float(wallet.balance) == 1250.0
