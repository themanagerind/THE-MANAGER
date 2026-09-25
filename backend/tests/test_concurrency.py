"""Duplicate/concurrent request tests — priority #4 per Section 42."""
import asyncio
import uuid
from datetime import date, datetime, timezone
from datetime import time as time_cls

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    HouseType, LocationType, MaintenanceDueStatus, PaymentStatus, RelationshipType, Role, UserStatus,
)
from app.models.identity import Property, PropertyResident, Society, SocietyLocation, User, UserRole
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


async def test_concurrent_withdraw_and_deciding_vote_never_both_succeed(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Audit fix: withdraw_proposal previously read the proposal with a
    plain (unlocked) SELECT, unlike cast_vote's row-locked one. A withdraw
    landing while the deciding vote's transaction was still in flight could
    read OPEN, then — once that vote committed APPROVED — blindly overwrite
    it back to WITHDRAWN on its own commit (a blind UPDATE with no check on
    the prior status), silently discarding the APPROVED outcome with BOTH
    calls returning 200. Locking withdraw_proposal too closes this: exactly
    one of the two calls can win."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]

    # A single dual-role (Resident + Sub-admin) voter, sole eligible voter
    # for both tallies, so their one APPROVE vote flips both thresholds
    # (100% >= 90% and 100% >= 80%) synchronously inside cast_vote.
    voter = User(society_id=society_id, full_name="Dual Voter", mobile="9300000200", status=UserStatus.ACTIVE)
    db_session.add(voter)
    await db_session.flush()
    db_session.add_all([
        UserRole(user_id=voter.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)),
        UserRole(user_id=voter.id, role=Role.SUB_ADMIN, assigned_at=datetime.now(timezone.utc)),
    ])
    await db_session.commit()

    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    resp = await client.post(
        "/api/v1/proposals",
        json={"scope_type": "SOCIETY", "title": "Repaint lobby", "description": "Repaint the main lobby"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    proposal_id = resp.json()["id"]

    voter_headers = auth_headers(voter.id, society_id, Role.SUB_ADMIN, [Role.SUB_ADMIN, Role.RESIDENT])

    vote_call = client.post(
        f"/api/v1/proposals/{proposal_id}/vote", json={"vote": "APPROVE"}, headers=voter_headers,
    )
    withdraw_call = client.post(f"/api/v1/proposals/{proposal_id}/withdraw", headers=admin_headers)
    vote_resp, withdraw_resp = await asyncio.gather(vote_call, withdraw_call)

    successes = [r.status_code for r in (vote_resp, withdraw_resp)].count(200)
    assert successes == 1, f"expected exactly one winner, got vote={vote_resp.status_code} withdraw={withdraw_resp.status_code}"

    resp = await client.get(f"/api/v1/proposals/{proposal_id}", headers=admin_headers)
    final_status = resp.json()["proposal"]["status"]
    if vote_resp.status_code == 200:
        assert final_status == "APPROVED"
    else:
        assert final_status == "WITHDRAWN"


async def test_concurrent_decide_booking_never_double_approves_overlapping_slots(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Audit fix: decide_booking's own "is another APPROVED booking already
    overlapping?" re-check was itself unlocked, so two Admins (or the same
    Admin in two tabs) approving two different, time-overlapping PENDING
    bookings at the same instant could both pass that check before either
    commits — two APPROVED, overlapping bookings for one amenity. Locking
    every PENDING/APPROVED booking for the amenity+date before the check
    closes this."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post("/api/v1/amenities", json={"name": "Clubhouse"}, headers=admin_headers)
    amenity_id = resp.json()["id"]

    loc = SocietyLocation(society_id=society_id, name="Wing CB", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()

    properties, residents = [], []
    for i in range(2):
        prop = Property(
            society_id=society_id, location_id=loc.id, house_number=f"CB-{i}",
            house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
        )
        db_session.add(prop)
        await db_session.flush()
        resident = User(society_id=society_id, full_name=f"CB Resident {i}", mobile=f"9300030{i:03d}", status=UserStatus.ACTIVE)
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
        properties.append(prop)
        residents.append(resident)

    resident0_headers = auth_headers(residents[0].id, society_id, Role.RESIDENT, [Role.RESIDENT])
    resp = await client.post(
        "/api/v1/amenities/bookings",
        json={
            "amenity_id": amenity_id, "property_id": str(properties[0].id), "booking_date": "2026-10-01",
            "start_time": "10:00:00", "end_time": "11:00:00",
        },
        headers=resident0_headers,
    )
    assert resp.status_code == 200
    booking_ids = [resp.json()["id"]]

    # A second, time-overlapping PENDING booking can't be created through
    # the API (create_booking's own overlap check blocks it) — simulate the
    # narrow window where one slipped in anyway (e.g. a genuine concurrent
    # double-create) by inserting it directly, same as
    # test_amenities.py::test_two_pending_bookings_for_the_same_slot_cannot_both_be_approved.
    from app.models.operations import AmenityBooking as _AmenityBooking
    other = _AmenityBooking(
        society_id=society_id, amenity_id=uuid.UUID(amenity_id), property_id=properties[1].id,
        resident_id=residents[1].id, booking_date=date(2026, 10, 1),
        start_time=time_cls(10, 30), end_time=time_cls(11, 30), status="PENDING",
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    booking_ids.append(str(other.id))

    results = await asyncio.gather(
        client.post(f"/api/v1/amenities/bookings/{booking_ids[0]}/decision", json={"approve": True}, headers=admin_headers),
        client.post(f"/api/v1/amenities/bookings/{booking_ids[1]}/decision", json={"approve": True}, headers=admin_headers),
    )
    status_codes = sorted(r.status_code for r in results)
    assert status_codes == [200, 409], f"expected exactly one approval to win, got {status_codes}"

    from app.models.operations import AmenityBooking
    approved = (
        await db_session.execute(
            select(AmenityBooking).where(
                AmenityBooking.id.in_([uuid.UUID(b) for b in booking_ids]), AmenityBooking.status == "APPROVED"
            )
        )
    ).scalars().all()
    assert len(approved) == 1


async def test_concurrent_unanimous_admin_change_approval_does_not_get_stuck(
    client: AsyncClient, db_session: AsyncSession
):
    """Audit fix: decide_admin_change_approval computed `done` (committed
    approvals) then added +1 to account for its own uncommitted decision —
    correct for a single caller, but under two truly concurrent decisions
    from different Sub-admins, each independently under-counts the other's
    not-yet-committed approval, so both compute done+1 < total and neither
    finalizes: the request is left stuck PENDING forever with every
    approval actually done. Locking the request row serializes the two
    decisions so the second always sees the first's committed state."""
    from app.models.enums import SocietyStatus

    society = Society(name="Concurrency Admin Change Society", code=f"SOC-CCADM-{uuid.uuid4().hex[:6]}", status=SocietyStatus.ACTIVE)
    db_session.add(society)
    await db_session.flush()

    owner = User(society_id=None, full_name="Owner", mobile=f"9{uuid.uuid4().hex[:9]}", status=UserStatus.ACTIVE)
    admin = User(society_id=society.id, full_name="Current Admin", mobile=f"9{uuid.uuid4().hex[:9]}", status=UserStatus.ACTIVE)
    db_session.add_all([owner, admin])
    await db_session.flush()
    db_session.add_all([
        UserRole(user_id=owner.id, role=Role.PLATFORM_OWNER, assigned_at=datetime.now(timezone.utc)),
        UserRole(user_id=admin.id, role=Role.ADMIN, assigned_at=datetime.now(timezone.utc)),
    ])

    subadmins = []
    for i in range(2):
        sa = User(society_id=society.id, full_name=f"CC Sub-admin {i}", mobile=f"9{uuid.uuid4().hex[:9]}", status=UserStatus.ACTIVE)
        db_session.add(sa)
        await db_session.flush()
        db_session.add(UserRole(user_id=sa.id, role=Role.SUB_ADMIN, assigned_at=datetime.now(timezone.utc)))
        subadmins.append(sa)
    await db_session.commit()

    owner_headers = auth_headers(owner.id, None, Role.PLATFORM_OWNER, [Role.PLATFORM_OWNER])
    resp = await client.post(
        "/api/v1/admin-change-requests",
        json={
            "society_id": str(society.id), "new_admin_full_name": "Incoming Admin",
            "new_admin_mobile": "9900000099", "new_admin_email": None,
        },
        headers=owner_headers,
    )
    assert resp.status_code == 200
    request_id = resp.json()["id"]

    sa_headers = [auth_headers(sa.id, society.id, Role.SUB_ADMIN, [Role.SUB_ADMIN]) for sa in subadmins]
    results = await asyncio.gather(
        client.post(f"/api/v1/admin-change-requests/{request_id}/decision", json={"approve": True}, headers=sa_headers[0]),
        client.post(f"/api/v1/admin-change-requests/{request_id}/decision", json={"approve": True}, headers=sa_headers[1]),
    )
    assert all(r.status_code == 200 for r in results), [r.status_code for r in results]

    resp = await client.get("/api/v1/admin-change-requests", headers=owner_headers)
    req = next(r for r in resp.json() if r["id"] == request_id)
    assert req["status"] == "APPROVED", f"request stuck at {req['status']} with approvals_done={req['approvals_done']}"
    assert req["approvals_done"] == 2
