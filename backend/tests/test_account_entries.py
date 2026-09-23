"""Account entries authorization — audit finding: GET /account-entries and
GET /account-entries/balance granted Manager the same visibility as
Admin/Sub-admin/Resident, but the finalized Manager finance requirement is
narrower — property-level maintenance dues only (payments.py's by-property
endpoint), never the society's full income/expense ledger or balance."""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, UserStatus
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
