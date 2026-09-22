"""
Shared test fixtures.

These tests require a REAL PostgreSQL and Redis instance (see
tests/README.md) — they exercise actual DB constraints (composite FKs,
partial unique indexes, row locking), which cannot be faithfully emulated
by SQLite or a mocked session. Point TEST_DATABASE_URL / TEST_REDIS_URL at
disposable instances; the schema is created fresh and dropped after each
test session.
"""
import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/housing_test"))
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("REDIS_URL", os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15"))

from app.core.db import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.core.redis_client import get_redis  # noqa: E402


@pytest_asyncio.fixture(scope="session")
async def _engine():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(_engine) -> AsyncSession:
    session_factory = async_sessionmaker(bind=_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def _flush_redis():
    r = get_redis()
    await r.flushdb()
    yield
    await r.flushdb()


@pytest_asyncio.fixture
async def client(_engine):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def two_societies_with_admins(client: AsyncClient, db_session: AsyncSession) -> dict:
    """Seeds two separate, ACTIVE societies each with an ACTIVE Admin —
    the baseline fixture for every cross-society isolation test."""
    from app.models.enums import SocietyStatus, UserStatus
    from app.models.identity import Society, User, UserRole
    from app.models.enums import Role
    from datetime import datetime, timezone

    result = {}
    for label in ("a", "b"):
        society = Society(name=f"Society {label.upper()}", code=f"SOC-{label}-{uuid.uuid4().hex[:6]}", status=SocietyStatus.ACTIVE)
        db_session.add(society)
        await db_session.flush()

        admin = User(
            society_id=society.id, full_name=f"Admin {label.upper()}",
            mobile=f"9{label}00000001", status=UserStatus.ACTIVE,
        )
        db_session.add(admin)
        await db_session.flush()
        db_session.add(UserRole(user_id=admin.id, role=Role.ADMIN, assigned_at=datetime.now(timezone.utc)))
        result[label] = {"society_id": society.id, "admin_id": admin.id}

    await db_session.commit()
    return result


def bearer_token_for(user_id: uuid.UUID, society_id: uuid.UUID | None, active_role, available_roles: list) -> str:
    """Test-only shortcut: issues a valid access token directly, bypassing
    the OTP flow, so tests can focus on the endpoint under test rather than
    re-deriving OTP delivery every time. The OTP flow itself is covered
    separately in test_auth.py."""
    from app.core.security import create_access_token

    return create_access_token(user_id, society_id, active_role, available_roles)


def auth_headers(user_id: uuid.UUID, society_id: uuid.UUID | None, active_role, available_roles: list) -> dict:
    token = bearer_token_for(user_id, society_id, active_role, available_roles)
    return {"Authorization": f"Bearer {token}"}
