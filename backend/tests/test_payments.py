"""Payment -> wallet -> ledger tests — priority #3 per Section 42."""
import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    HouseType, LocationType, MaintenanceDueStatus, RelationshipType, Role, UserStatus,
)
from app.models.identity import Property, PropertyResident, SocietyLocation, User, UserRole
from app.models.payments import MaintenanceDue, Payment, Wallet, WalletTransaction
from app.models.accounts import AccountEntry
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_resident_with_property(db_session: AsyncSession, society_id):
    loc = SocietyLocation(society_id=society_id, name="Wing A", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()
    prop = Property(
        society_id=society_id, location_id=loc.id, house_number="201",
        house_type=HouseType.FLAT, floor_number=2, status="ACTIVE",
    )
    db_session.add(prop)
    await db_session.flush()

    resident = User(society_id=society_id, full_name="Resident", mobile="9200000001", status=UserStatus.ACTIVE)
    db_session.add(resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    db_session.add(
        PropertyResident(
            society_id=society_id, property_id=prop.id, resident_id=resident.id,
            relationship_type=RelationshipType.OWNER, is_active=True, created_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()
    await db_session.refresh(prop)
    await db_session.refresh(resident)
    return prop, resident


async def _seed_due(db_session: AsyncSession, society_id, property_id, amount=2500.0) -> MaintenanceDue:
    now = datetime.now(timezone.utc)
    due = MaintenanceDue(
        society_id=society_id, property_id=property_id, amount=amount, due_date=date.today(),
        status=MaintenanceDueStatus.PENDING, billing_month=date.today().replace(day=1),
        generated_at=now, updated_at=now,
    )
    db_session.add(due)
    await db_session.commit()
    await db_session.refresh(due)
    return due


async def test_mock_online_payment_credits_wallet_and_ledger_exactly_once(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    prop, resident = await _seed_resident_with_property(db_session, society_id)
    due = await _seed_due(db_session, society_id, prop.id, amount=3000.0)

    headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.post(
        "/api/v1/payments",
        json={
            "maintenance_due_id": str(due.id), "payment_method": "MOCK_ONLINE",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "PAID"
    payment_id = body["id"]

    await db_session.refresh(due)
    assert due.status == MaintenanceDueStatus.PAID

    wallet = (await db_session.execute(select(Wallet).where(Wallet.resident_id == resident.id))).scalar_one()
    assert float(wallet.balance) == 3000.0

    credits = (
        await db_session.execute(
            select(WalletTransaction).where(WalletTransaction.payment_id == uuid.UUID(payment_id))
        )
    ).scalars().all()
    assert len(credits) == 1  # exactly once

    ledger_entries = (
        await db_session.execute(select(AccountEntry).where(AccountEntry.related_payment_id == uuid.UUID(payment_id)))
    ).scalars().all()
    assert len(ledger_entries) == 1  # exactly once
    assert float(ledger_entries[0].amount) == 3000.0


async def test_manual_payment_without_proof_rejected(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    society_id = two_societies_with_admins["a"]["society_id"]
    prop, resident = await _seed_resident_with_property(db_session, society_id)
    due = await _seed_due(db_session, society_id, prop.id)

    headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.post(
        "/api/v1/payments",
        json={
            "maintenance_due_id": str(due.id), "payment_method": "MANUAL_UPI",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert resp.status_code == 400


async def test_duplicate_idempotency_key_returns_same_payment_not_a_duplicate(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Simulates an offline background-sync retry (Section 37)."""
    society_id = two_societies_with_admins["a"]["society_id"]
    prop, resident = await _seed_resident_with_property(db_session, society_id)
    due = await _seed_due(db_session, society_id, prop.id)

    headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    key = str(uuid.uuid4())
    payload = {
        "maintenance_due_id": str(due.id), "payment_method": "MANUAL_UPI", "idempotency_key": key,
        "proof_type": "UPI_SCREENSHOT", "proof_file_url": "https://example.com/proof.png",
    }
    resp1 = await client.post("/api/v1/payments", json=payload, headers=headers)
    assert resp1.status_code == 200

    resp2 = await client.post("/api/v1/payments", json=payload, headers=headers)
    assert resp2.status_code == 409

    payments = (
        await db_session.execute(select(Payment).where(Payment.maintenance_due_id == due.id))
    ).scalars().all()
    assert len(payments) == 1


async def test_second_payment_blocked_while_one_is_pending(client: AsyncClient, db_session: AsyncSession, two_societies_with_admins):
    """Section 49.2 — at most one PENDING_APPROVAL payment per due."""
    society_id = two_societies_with_admins["a"]["society_id"]
    prop, resident = await _seed_resident_with_property(db_session, society_id)
    due = await _seed_due(db_session, society_id, prop.id)

    headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp1 = await client.post(
        "/api/v1/payments",
        json={
            "maintenance_due_id": str(due.id), "payment_method": "MANUAL_CASH",
            "idempotency_key": str(uuid.uuid4()), "proof_type": "CASH_RECEIPT",
            "proof_file_url": "https://example.com/receipt.png",
        },
        headers=headers,
    )
    assert resp1.status_code == 200

    resp2 = await client.post(
        "/api/v1/payments",
        json={
            "maintenance_due_id": str(due.id), "payment_method": "MANUAL_CASH",
            "idempotency_key": str(uuid.uuid4()), "proof_type": "CASH_RECEIPT",
            "proof_file_url": "https://example.com/receipt2.png",
        },
        headers=headers,
    )
    assert resp2.status_code == 409


async def test_payment_correction_creates_adjustment_not_new_payment(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    prop, resident = await _seed_resident_with_property(db_session, society_id)
    due = await _seed_due(db_session, society_id, prop.id, amount=5000.0)

    resident_headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.post(
        "/api/v1/payments",
        json={"maintenance_due_id": str(due.id), "payment_method": "MOCK_ONLINE", "idempotency_key": str(uuid.uuid4())},
        headers=resident_headers,
    )
    payment_id = resp.json()["id"]

    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    resp = await client.post(
        f"/api/v1/payments/{payment_id}/correct",
        json={"new_amount": 4500.0, "reason": "Overbilled by mistake"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["difference"] == -500.0

    payment = (await db_session.execute(select(Payment).where(Payment.id == uuid.UUID(payment_id)))).scalar_one()
    assert float(payment.amount) == 4500.0

    wallet = (await db_session.execute(select(Wallet).where(Wallet.resident_id == resident.id))).scalar_one()
    assert float(wallet.balance) == 4500.0
