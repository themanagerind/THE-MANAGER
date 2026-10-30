"""Expense bill approval flow — Section 23. No test coverage existed for
this module at all before this file (audit finding): a full unanimous-
Sub-admin-approval money workflow with zero automated tests.

Also covers the audit fix for a real stuck-bill bug: nothing previously
stopped an Admin from demoting (or approving the resignation of) the last
active Sub-admin while an expense bill was PENDING_APPROVAL. Once active
Sub-admin count hits 0, the bill can never be approved (0 active means the
100% threshold can never be met) or rejected (decide_approval requires an
active Sub-admin caller, and none exist), leaving it permanently stuck."""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, UserStatus
from app.models.identity import User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_subadmins(db_session: AsyncSession, society_id, count: int = 1) -> list[User]:
    subadmins = []
    for i in range(count):
        sa = User(society_id=society_id, full_name=f"EB SubAdmin {i}", mobile=f"9600000{i:03d}", status=UserStatus.ACTIVE)
        db_session.add(sa)
        await db_session.flush()
        db_session.add(UserRole(user_id=sa.id, role=Role.SUB_ADMIN, assigned_at=datetime.now(timezone.utc)))
        subadmins.append(sa)
    await db_session.commit()
    return subadmins


async def test_admin_finalize_and_single_subadmin_approve_approves_bill(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    subadmins = await _seed_subadmins(db_session, society_id, 1)

    resp = await client.post(
        "/api/v1/expense-bills", json={"title": "Lift AMC", "amount": 5000.0, "bill_image_key": "expense_bill_proofs/test.jpg"}, headers=admin_headers,
    )
    assert resp.status_code == 200
    bill_id = resp.json()["id"]
    assert resp.json()["status"] == "PENDING_APPROVAL"

    subadmin_headers = auth_headers(subadmins[0].id, society_id, Role.SUB_ADMIN, [Role.SUB_ADMIN])
    resp = await client.post(
        f"/api/v1/expense-bills/{bill_id}/decision", json={"decision": "APPROVE"}, headers=subadmin_headers,
    )
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/expense-bills/{bill_id}", headers=admin_headers)
    assert resp.json()["bill"]["status"] == "APPROVED"


async def test_single_reject_is_immediate_and_final(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    subadmins = await _seed_subadmins(db_session, society_id, 2)

    resp = await client.post(
        "/api/v1/expense-bills", json={"title": "Painting", "amount": 20000.0, "bill_image_key": "expense_bill_proofs/test.jpg"}, headers=admin_headers,
    )
    bill_id = resp.json()["id"]

    headers0 = auth_headers(subadmins[0].id, society_id, Role.SUB_ADMIN, [Role.SUB_ADMIN])
    resp = await client.post(
        f"/api/v1/expense-bills/{bill_id}/decision",
        json={"decision": "REJECT", "reason": "Too expensive"}, headers=headers0,
    )
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/expense-bills/{bill_id}", headers=admin_headers)
    assert resp.json()["bill"]["status"] == "REJECTED"

    # The other Sub-admin can no longer decide — already resolved.
    headers1 = auth_headers(subadmins[1].id, society_id, Role.SUB_ADMIN, [Role.SUB_ADMIN])
    resp = await client.post(
        f"/api/v1/expense-bills/{bill_id}/decision", json={"decision": "APPROVE"}, headers=headers1,
    )
    assert resp.status_code == 409


async def test_demoting_last_active_subadmin_blocked_while_bill_pending(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """The stuck-bill bug this fix prevents: without the guard, this
    demote call would succeed, leaving the PENDING_APPROVAL bill with 0
    active Sub-admins — unable to ever be approved or rejected."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    subadmins = await _seed_subadmins(db_session, society_id, 1)

    resp = await client.post(
        "/api/v1/expense-bills", json={"title": "Elevator repair", "amount": 15000.0, "bill_image_key": "expense_bill_proofs/test.jpg"}, headers=admin_headers,
    )
    bill_id = resp.json()["id"]
    assert resp.json()["status"] == "PENDING_APPROVAL"

    resp = await client.delete(f"/api/v1/subadmins/{subadmins[0].id}", headers=admin_headers)
    assert resp.status_code == 409

    # Once the bill is resolved, demoting the same Sub-admin is fine again.
    subadmin_headers = auth_headers(subadmins[0].id, society_id, Role.SUB_ADMIN, [Role.SUB_ADMIN])
    resp = await client.post(
        f"/api/v1/expense-bills/{bill_id}/decision", json={"decision": "APPROVE"}, headers=subadmin_headers,
    )
    assert resp.status_code == 200

    resp = await client.delete(f"/api/v1/subadmins/{subadmins[0].id}", headers=admin_headers)
    assert resp.status_code == 204


async def test_create_and_finalize_rejects_when_zero_active_subadmins(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/expense-bills", json={"title": "No subadmins yet", "amount": 100.0, "bill_image_key": "expense_bill_proofs/test.jpg"}, headers=admin_headers,
    )
    assert resp.status_code == 409


async def test_approving_last_subadmins_resignation_blocked_while_bill_pending(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Same stuck-bill guard as demote_subadmin, on the other path that
    revokes SUB_ADMIN: an Admin approving a resignation request."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    subadmins = await _seed_subadmins(db_session, society_id, 1)
    subadmin_headers = auth_headers(subadmins[0].id, society_id, Role.SUB_ADMIN, [Role.SUB_ADMIN])

    resp = await client.post(
        "/api/v1/expense-bills", json={"title": "Gate repair", "amount": 8000.0, "bill_image_key": "expense_bill_proofs/test.jpg"}, headers=admin_headers,
    )
    assert resp.status_code == 200

    resp = await client.post("/api/v1/subadmins/resignation", json={}, headers=subadmin_headers)
    assert resp.status_code == 200
    request_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/subadmins/resignations/{request_id}/decision", json={"approve": True}, headers=admin_headers,
    )
    assert resp.status_code == 409


async def test_bill_image_is_mandatory(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Redesign (user-requested): every new bill must carry a photo of the
    physical bill — reverses the old "never required" v1.1 decision."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    await _seed_subadmins(db_session, society_id, 1)

    resp = await client.post(
        "/api/v1/expense-bills", json={"title": "No image bill", "amount": 100.0}, headers=admin_headers,
    )
    assert resp.status_code == 422


async def test_approval_no_longer_auto_posts_to_accounts(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Redesign (user-requested): APPROVED no longer creates an
    AccountEntry by itself — Admin settles it manually from Accounts."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    subadmins = await _seed_subadmins(db_session, society_id, 1)

    resp = await client.post(
        "/api/v1/expense-bills",
        json={"title": "AMC no autopost", "amount": 7000.0, "bill_image_key": "expense_bill_proofs/test.jpg"},
        headers=admin_headers,
    )
    bill_id = resp.json()["id"]

    subadmin_headers = auth_headers(subadmins[0].id, society_id, Role.SUB_ADMIN, [Role.SUB_ADMIN])
    resp = await client.post(
        f"/api/v1/expense-bills/{bill_id}/decision", json={"decision": "APPROVE"}, headers=subadmin_headers,
    )
    assert resp.status_code == 200

    resp = await client.get("/api/v1/account-entries", headers=admin_headers)
    assert resp.status_code == 200
    assert all(e["source"] != "EXPENSE_BILL" for e in resp.json()["items"])

    resp = await client.get("/api/v1/account-entries/pending-expense-bills", headers=admin_headers)
    assert resp.status_code == 200
    assert any(b["id"] == bill_id for b in resp.json())
