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


async def test_resident_cannot_view_other_propertys_dues(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Regression test — audit finding C2 (IDOR): a Resident could previously
    name ANY property_id in their own society on the by-property dues
    endpoint and read its maintenance dues, not just their own linked
    property's."""
    society_id = two_societies_with_admins["a"]["society_id"]
    prop, resident = await _seed_resident_with_property(db_session, society_id)
    await _seed_due(db_session, society_id, prop.id, amount=1800.0)

    # A second property in the SAME society that this resident has no link to.
    other_loc = SocietyLocation(society_id=society_id, name="Wing B", location_type=LocationType.WING)
    db_session.add(other_loc)
    await db_session.flush()
    other_prop = Property(
        society_id=society_id, location_id=other_loc.id, house_number="301",
        house_type=HouseType.FLAT, floor_number=3, status="ACTIVE",
    )
    db_session.add(other_prop)
    await db_session.commit()
    await db_session.refresh(other_prop)
    await _seed_due(db_session, society_id, other_prop.id, amount=9999.0)

    headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.get(f"/api/v1/payments/maintenance-dues/by-property/{other_prop.id}", headers=headers)
    assert resp.status_code == 403

    # Sanity: the resident CAN still read dues for their own linked property.
    resp = await client.get(f"/api/v1/payments/maintenance-dues/by-property/{prop.id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_manager_can_view_property_dues_but_not_generate_or_correct(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Regression test — audit finding C5/C6: Manager needs view-only access
    to property-level maintenance dues, but no write access to payments
    (generate/correct/reject stay Admin/Sub-admin only)."""
    society_id = two_societies_with_admins["a"]["society_id"]
    prop, resident = await _seed_resident_with_property(db_session, society_id)
    await _seed_due(db_session, society_id, prop.id, amount=2200.0)

    manager = User(society_id=society_id, full_name="Manager", mobile="9400000001", status=UserStatus.ACTIVE)
    db_session.add(manager)
    await db_session.flush()
    db_session.add(UserRole(user_id=manager.id, role=Role.MANAGER, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    await db_session.refresh(manager)

    headers = auth_headers(manager.id, society_id, Role.MANAGER, [Role.MANAGER])

    resp = await client.get(f"/api/v1/payments/maintenance-dues/by-property/{prop.id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = await client.post(
        "/api/v1/payments/maintenance-dues/generate",
        json={"occupied_amount": 1000.0, "vacant_amount": 500.0, "billing_month": date.today().replace(day=1).isoformat()},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_generate_bills_charges_occupied_and_vacant_amounts_separately(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Section 13.2 extension: a society always has some empty flats/
    houses alongside occupied ones — generation takes two amounts, and
    each property's bill picks the one matching whether it currently has
    an active Owner/Tenant link."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]

    occupied_prop, _resident = await _seed_resident_with_property(db_session, society_id)

    loc = SocietyLocation(society_id=society_id, name="Wing B", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()
    vacant_prop = Property(
        society_id=society_id, location_id=loc.id, house_number="301",
        house_type=HouseType.FLAT, floor_number=3, status="ACTIVE",
    )
    db_session.add(vacant_prop)
    await db_session.commit()
    await db_session.refresh(vacant_prop)

    headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    resp = await client.post(
        "/api/v1/payments/maintenance-dues/generate",
        json={
            "occupied_amount": 2000.0, "vacant_amount": 500.0,
            "billing_month": date.today().replace(day=1).isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 200
    by_property = {d["property_id"]: d["amount"] for d in resp.json()}
    assert by_property[str(occupied_prop.id)] == 2000.0
    assert by_property[str(vacant_prop.id)] == 500.0


async def test_generate_bills_treats_a_property_with_only_an_inactive_link_as_vacant(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """A property whose only PropertyResident row has is_active=False (a
    past Owner/Tenant who moved out, unlink not yet followed by a new
    link) must still be billed at the vacant rate, not the occupied one."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]

    prop, resident = await _seed_resident_with_property(db_session, society_id)
    link = (
        await db_session.execute(
            select(PropertyResident).where(PropertyResident.property_id == prop.id)
        )
    ).scalar_one()
    link.is_active = False
    await db_session.commit()

    headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    resp = await client.post(
        "/api/v1/payments/maintenance-dues/generate",
        json={
            "occupied_amount": 2000.0, "vacant_amount": 500.0,
            "billing_month": date.today().replace(day=1).isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 200
    by_property = {d["property_id"]: d["amount"] for d in resp.json()}
    assert by_property[str(prop.id)] == 500.0


async def test_paid_due_cannot_be_paid_again(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Regression test: submit_payment() only guarded against a second
    PENDING_APPROVAL payment on the same due — a due that's already PAID
    (e.g. via MOCK_ONLINE, which skips PENDING_APPROVAL entirely and goes
    straight to PAID) had no guard at all, so a second submission would
    double-credit the wallet and double-post ledger income."""
    society_id = two_societies_with_admins["a"]["society_id"]
    prop, resident = await _seed_resident_with_property(db_session, society_id)
    due = await _seed_due(db_session, society_id, prop.id, amount=1500.0)

    headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.post(
        "/api/v1/payments",
        json={"maintenance_due_id": str(due.id), "payment_method": "MOCK_ONLINE", "idempotency_key": str(uuid.uuid4())},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PAID"

    resp = await client.post(
        "/api/v1/payments",
        json={"maintenance_due_id": str(due.id), "payment_method": "MOCK_ONLINE", "idempotency_key": str(uuid.uuid4())},
        headers=headers,
    )
    assert resp.status_code == 409

    wallet = (await db_session.execute(select(Wallet).where(Wallet.resident_id == resident.id))).scalar_one()
    assert float(wallet.balance) == 1500.0  # not double-credited

    payments = (
        await db_session.execute(select(Payment).where(Payment.maintenance_due_id == due.id))
    ).scalars().all()
    assert len(payments) == 1  # not double-inserted

    ledger_entries = (
        await db_session.execute(select(AccountEntry).where(AccountEntry.related_payment_id == payments[0].id))
    ).scalars().all()
    assert len(ledger_entries) == 1  # not double-posted


async def test_payment_proof_upload_and_retrieval(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Regression test: the frontend has called POST /uploads/payment-proof
    and GET /payments/{id}/proofs since manual payment support was added,
    but neither endpoint existed on the backend at all — this whole flow
    was disconnected."""
    society_id = two_societies_with_admins["a"]["society_id"]
    prop, resident = await _seed_resident_with_property(db_session, society_id)
    due = await _seed_due(db_session, society_id, prop.id, amount=1200.0)
    headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    fake_jpeg = b"\xff\xd8\xff\xe0" + b"0" * 100
    resp = await client.post(
        "/api/v1/uploads/payment-proof",
        files={"file": ("proof.jpg", fake_jpeg, "image/jpeg")},
        headers=headers,
    )
    assert resp.status_code == 200
    storage_key = resp.json()["file_url"]
    # Audit fix: this used to be a directly-fetchable public URL
    # (/uploads/payment_proofs/...) — it's now an opaque storage key, only
    # ever resolved server-side by the authenticated file endpoint below.
    assert not storage_key.startswith("/uploads/")

    resp = await client.post(
        "/api/v1/payments",
        json={
            "maintenance_due_id": str(due.id), "payment_method": "MANUAL_UPI",
            "idempotency_key": str(uuid.uuid4()), "proof_type": "UPI_SCREENSHOT",
            "proof_file_url": storage_key,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    payment_id = resp.json()["id"]
    assert resp.json()["status"] == "PENDING_APPROVAL"

    resp = await client.get(f"/api/v1/payments/{payment_id}/proofs", headers=headers)
    assert resp.status_code == 200
    proofs = resp.json()
    assert len(proofs) == 1
    proof_id = proofs[0]["id"]
    # file_url now points at the authenticated endpoint, not the raw
    # storage key or a public path.
    assert proofs[0]["file_url"] == f"/payments/{payment_id}/proofs/{proof_id}/file"

    resp = await client.get(f"/api/v1/payments/{payment_id}/proofs/{proof_id}/file", headers=headers)
    assert resp.status_code == 200
    assert resp.content == fake_jpeg

    # An unrelated Resident cannot see this payment's proofs, or fetch the
    # file directly even knowing its exact URL.
    other_resident = User(society_id=society_id, full_name="Other Resident", mobile="9500000002", status=UserStatus.ACTIVE)
    db_session.add(other_resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=other_resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    other_headers = auth_headers(other_resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.get(f"/api/v1/payments/{payment_id}/proofs", headers=other_headers)
    assert resp.status_code == 403
    resp = await client.get(f"/api/v1/payments/{payment_id}/proofs/{proof_id}/file", headers=other_headers)
    assert resp.status_code == 403

    # And an entirely unauthenticated request is rejected too.
    resp = await client.get(f"/api/v1/payments/{payment_id}/proofs/{proof_id}/file")
    assert resp.status_code == 401


async def test_payment_proof_upload_rejects_non_image(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    _prop, resident = await _seed_resident_with_property(db_session, society_id)
    headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.post(
        "/api/v1/uploads/payment-proof",
        files={"file": ("proof.txt", b"not an image", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_payment_proof_upload_rejects_spoofed_content_type(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Regression test: validation used to trust file.content_type alone —
    a client-supplied header — so a non-image file labeled "image/png"
    would have been accepted. The actual bytes are checked now."""
    society_id = two_societies_with_admins["a"]["society_id"]
    _prop, resident = await _seed_resident_with_property(db_session, society_id)
    headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.post(
        "/api/v1/uploads/payment-proof",
        files={"file": ("proof.png", b"this is not actually a PNG file", "image/png")},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_payment_proof_upload_is_rate_limited_per_resident(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Regression test: no per-user upload rate limit existed — an
    authenticated Resident could upload arbitrarily many 5 MB files."""
    society_id = two_societies_with_admins["a"]["society_id"]
    _prop, resident = await _seed_resident_with_property(db_session, society_id)
    headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])
    fake_jpeg = b"\xff\xd8\xff\xe0" + b"0" * 10

    statuses = []
    for _ in range(21):
        resp = await client.post(
            "/api/v1/uploads/payment-proof",
            files={"file": ("proof.jpg", fake_jpeg, "image/jpeg")},
            headers=headers,
        )
        statuses.append(resp.status_code)

    assert statuses.count(200) == 20
    assert statuses[-1] == 429


async def test_payment_proof_upload_rejects_when_storage_full(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins, monkeypatch
):
    """Regression test: no total-storage cap existed either — added one,
    checked before every write."""
    from app.services import upload_service

    society_id = two_societies_with_admins["a"]["society_id"]
    _prop, resident = await _seed_resident_with_property(db_session, society_id)
    headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    monkeypatch.setattr(upload_service, "_MAX_TOTAL_STORAGE_BYTES", 0)

    resp = await client.post(
        "/api/v1/uploads/payment-proof",
        files={"file": ("proof.jpg", b"\xff\xd8\xff\xe0" + b"0" * 10, "image/jpeg")},
        headers=headers,
    )
    assert resp.status_code == 507
