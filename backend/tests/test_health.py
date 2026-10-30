"""Health/readiness endpoints — Section 41. No test coverage existed for
either before this; found while auditing the app for production-readiness
gaps (GET /health reported "ok" even with Postgres/Redis unreachable,
which /health/ready was added to fix)."""
import pytest
from httpx import AsyncClient

import app.main as main_module

pytestmark = pytest.mark.asyncio


async def test_health_is_always_ok(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_health_ready_reports_ready_when_db_and_redis_are_up(client: AsyncClient):
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


async def test_health_ready_reports_503_when_redis_is_unreachable(client: AsyncClient, monkeypatch):
    class _BrokenRedis:
        async def ping(self):
            raise ConnectionError("simulated Redis outage")

    monkeypatch.setattr(main_module, "get_redis", lambda: _BrokenRedis())

    resp = await client.get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not ready"
    assert body["unreachable"] == ["redis"]
