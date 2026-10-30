import pytest
from httpx import AsyncClient

import app.api.v1.auth as auth_module


@pytest.fixture(autouse=True)
def _no_real_sms(monkeypatch):
    async def noop(mobile, otp):
        pass

    monkeypatch.setattr(auth_module, "send_otp_sms", noop)


async def test_otp_not_echoed_in_production_by_default(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(auth_module.settings, "environment", "production")
    monkeypatch.setattr(auth_module.settings, "show_otp_on_screen", False)

    resp = await client.post("/api/v1/auth/otp/request", json={"mobile": "9000000201"})

    assert resp.status_code == 200
    assert resp.json()["dev_otp"] is None


async def test_otp_echoed_in_production_when_flag_on(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(auth_module.settings, "environment", "production")
    monkeypatch.setattr(auth_module.settings, "show_otp_on_screen", True)

    resp = await client.post("/api/v1/auth/otp/request", json={"mobile": "9000000202"})

    assert resp.status_code == 200
    otp = resp.json()["dev_otp"]
    assert otp and otp.isdigit()
