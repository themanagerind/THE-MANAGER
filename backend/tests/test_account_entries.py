"""Account entries authorization — audit finding: GET /account-entries and
GET /account-entries/balance granted Manager the same visibility as
Admin/Sub-admin/Resident, but the finalized Manager finance requirement is
narrower — property-level maintenance dues only (payments.py's by-property
endpoint), never the society's full income/expense ledger or balance."""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounts import AccountHeading
from app.models.enums import EntryType, Role, UserStatus
from app.models.identity import User, UserRole
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_manager(db_session: AsyncSession, society_id, mobile: str) -> User:
    manager = User(society_id=society_id, full_name="Manager", mobile=mobile, status=UserStatus.ACTIVE)
    db_session.add(manager)
    await db_session.flush()
    db_session.add(UserRole(user_id=manager.id, role=Role.MANAGER, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    await db_session.refresh(manager)
    return manager


async def test_manager_cannot_list_account_entries(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    manager = await _seed_manager(db_session, society_id, "9500000001")
    headers = auth_headers(manager.id, society_id, Role.MANAGER, [Role.MANAGER])

    resp = await client.get("/api/v1/account-entries", headers=headers)
    assert resp.status_code == 403


async def test_manager_cannot_read_account_balance(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    manager = await _seed_manager(db_session, society_id, "9500000002")
    headers = auth_headers(manager.id, society_id, Role.MANAGER, [Role.MANAGER])

    resp = await client.get("/api/v1/account-entries/balance", headers=headers)
    assert resp.status_code == 403


async def test_admin_and_resident_can_still_read_account_entries(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Regression guard — the Manager restriction must not have collapsed
    into over-broad, breaking Admin/Resident's own still-intended access."""
    fixtures = two_societies_with_admins
    admin_headers = auth_headers(
        fixtures["a"]["admin_id"], fixtures["a"]["society_id"], Role.ADMIN, [Role.ADMIN]
    )
    resp = await client.get("/api/v1/account-entries", headers=admin_headers)
    assert resp.status_code == 200
    resp = await client.get("/api/v1/account-entries/balance", headers=admin_headers)
    assert resp.status_code == 200


async def _seed_heading(db_session: AsyncSession, entry_type: EntryType, title: str) -> AccountHeading:
    """Test DB is built via Base.metadata.create_all (tests/conftest.py),
    not `alembic upgrade head` — migration 0015's seed data never lands
    here, so tests seed their own headings directly instead of assuming
    the universal catalog is present."""
    heading = AccountHeading(entry_type=entry_type, title=title)
    db_session.add(heading)
    await db_session.commit()
    await db_session.refresh(heading)
    return heading


async def test_admin_creates_manual_entry_from_a_heading(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    """Title is no longer free-typed — it's taken from whichever heading
    Admin picks."""
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    heading = await _seed_heading(db_session, EntryType.INCOME, "Society Maintenance Charges")

    resp = await client.get("/api/v1/account-entries/headings", params={"entry_type": "INCOME"}, headers=admin_headers)
    assert resp.status_code == 200
    assert any(h["title"] == "Society Maintenance Charges" for h in resp.json())

    resp = await client.post(
        "/api/v1/account-entries",
        json={"entry_type": "INCOME", "heading_id": str(heading.id), "amount": 5000, "entry_date": "2026-09-01"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Society Maintenance Charges"
    assert body["heading_id"] == str(heading.id)


async def test_heading_entry_type_mismatch_rejected(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    expense_heading = await _seed_heading(db_session, EntryType.EXPENSE, "Lift Maintenance")

    resp = await client.post(
        "/api/v1/account-entries",
        json={"entry_type": "INCOME", "heading_id": str(expense_heading.id), "amount": 500, "entry_date": "2026-09-01"},
        headers=admin_headers,
    )
    assert resp.status_code == 400


async def test_admin_adds_custom_heading_and_reusing_it_is_idempotent(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post(
        "/api/v1/account-entries/headings", json={"entry_type": "EXPENSE", "title": "Diwali Decoration"}, headers=admin_headers
    )
    assert resp.status_code == 200
    first_id = resp.json()["id"]

    # Adding the exact same (entry_type, title) again must not error or
    # duplicate — it returns the same existing row.
    resp = await client.post(
        "/api/v1/account-entries/headings", json={"entry_type": "EXPENSE", "title": "Diwali Decoration"}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == first_id

    resp = await client.get("/api/v1/account-entries/headings", params={"entry_type": "EXPENSE"}, headers=admin_headers)
    assert sum(1 for h in resp.json() if h["title"] == "Diwali Decoration") == 1


async def test_editing_entry_heading_updates_title_and_is_tracked(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    admin_id = two_societies_with_admins["a"]["admin_id"]
    admin_headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])
    heading_a = await _seed_heading(db_session, EntryType.EXPENSE, "Lift Maintenance (edit test)")
    heading_b = await _seed_heading(db_session, EntryType.EXPENSE, "Pest Control (edit test)")

    resp = await client.post(
        "/api/v1/account-entries",
        json={"entry_type": "EXPENSE", "heading_id": str(heading_a.id), "amount": 2000, "entry_date": "2026-09-01"},
        headers=admin_headers,
    )
    entry_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/account-entries/{entry_id}", json={"heading_id": str(heading_b.id)}, headers=admin_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Pest Control (edit test)"
    assert body["heading_id"] == str(heading_b.id)
    assert body["is_edited"] is True


async def test_resident_cannot_manage_headings(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    resident = User(society_id=society_id, full_name="Resident", mobile="9500000010", status=UserStatus.ACTIVE)
    db_session.add(resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    await db_session.commit()
    resident_headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.get("/api/v1/account-entries/headings", headers=resident_headers)
    assert resp.status_code == 403
    resp = await client.post(
        "/api/v1/account-entries/headings", json={"entry_type": "INCOME", "title": "Made up"}, headers=resident_headers
    )
    assert resp.status_code == 403
