"""Duplicate/concurrent request tests — priority #4 per Section 42."""
import asyncio
import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, MaintenanceDueStatus, PaymentStatus, Role, UserStatus
from app.models.identity import Property, SocietyLocation, User, UserRole
from app.models.payments import MaintenanceDue, Payment
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def test_two_concurrent_approve_calls_only_one_succeeds(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Simulates an Admin and a Sub-admin both clicking 'approve' on the
    same payment at nearly the same instant — the row lock in
    approve_payment (Transactions hardening) must ensure exactly one call
    succeeds and the second sees a clean 409, never a double-credit."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]

    loc = SocietyLocation(society_id=society_id, name="Wing A", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()
    prop = Property(
        society_id=society_id, location_id=loc.id, house_number="301",
        house_type=HouseType.FLAT, floor_number=3, status="ACTIVE",
    )
    db_session.add(prop)
    await db_session.flush()

    resident = User(society_id=society_id, full_name="Resident", mobile="9300000001", status=UserStatus.ACTIVE)
    db_session.add(resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))

    now = datetime.now(timezone.utc)
    due = MaintenanceDue(
        society_id=society_id, property_id=prop.id, amount=1000.0, due_date=date.today(),
        status=MaintenanceDueStatus.PENDING, billing_month=date.today().replace(day=1),
        generated_at=now, updated_at=now,
    )
    db_session.add(due)
    await db_session.flush()

    payment = Payment(
        society_id=society_id, maintenance_due_id=due.id, property_id=prop.id, resident_id=resident.id,
        payment_method="MANUAL_CASH", amount=1000.0, status=PaymentStatus.PENDING_APPROVAL,
        idempotency_key=uuid.uuid4(), paid_marked_at=now,
    )
    db_session.add(payment)
    await db_session.commit()
    await db_session.refresh(payment)

    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    results = await asyncio.gather(
        client.post(f"/api/v1/payments/{payment.id}/approve", headers=admin_headers),
        client.post(f"/api/v1/payments/{payment.id}/approve", headers=admin_headers),
        return_exceptions=True,
    )
    status_codes = sorted(r.status_code if not isinstance(r, Exception) else -1 for r in results)
    assert status_codes.count(200) == 1, f"expected exactly one success, got {status_codes}"

    from app.models.payments import WalletTransaction
    credits = (
        await db_session.execute(select(WalletTransaction).where(WalletTransaction.payment_id == payment.id))
    ).scalars().all()
    assert len(credits) == 1  # never double-credited regardless of request interleaving


async def test_concurrent_proposal_votes_settle_to_consistent_count(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Multiple Residents voting on the same proposal concurrently must all
    be counted — the proposal-row lock (Transactions hardening) serializes
    the read-recompute-write cycle so no vote is lost to a race."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]

    subadmin = User(society_id=society_id, full_name="SubAdmin", mobile="9300000099", status=UserStatus.ACTIVE)
    db_session.add(subadmin)
    await db_session.flush()
    db_session.add(UserRole(user_id=subadmin.id, role=Role.SUB_ADMIN, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()

    residents = []
    for i in range(5):
        r = User(society_id=society_id, full_name=f"R{i}", mobile=f"93000001{i:02d}", status=UserStatus.ACTIVE)
        db_session.add(r)
        await db_session.flush()
        db_session.add(UserRole(user_id=r.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
        residents.append(r)
    await db_session.commit()

    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    resp = await client.post(
        "/api/v1/proposals",
        json={"scope_type": "SOCIETY", "title": "New gate", "description": "Install a new gate"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    proposal_id = resp.json()["id"]

    vote_calls = [
        client.post(
            f"/api/v1/proposals/{proposal_id}/vote",
            json={"vote": "APPROVE"},
            headers=auth_headers(r.id, society_id, Role.RESIDENT, [Role.RESIDENT]),
        )
        for r in residents
    ]
    results = await asyncio.gather(*vote_calls, return_exceptions=True)
    successes = [r for r in results if not isinstance(r, Exception) and r.status_code == 200]
    assert len(successes) == 5

    from app.models.governance import ProposalVote
    vote_rows = (
        await db_session.execute(select(ProposalVote).where(ProposalVote.proposal_id == uuid.UUID(proposal_id)))
    ).scalars().all()
    assert len(vote_rows) == 5
