from types import SimpleNamespace

from app.services import sms_service

TWILIO = dict(
    twilio_account_sid="ACxxx", twilio_auth_token="tok", twilio_from_number="+10000000000"
)
MSG91 = dict(msg91_auth_key="key", msg91_template_id="tmpl")


def _settings(**overrides):
    base = dict(
        sms_provider="auto",
        msg91_auth_key=None,
        msg91_template_id=None,
        twilio_account_sid=None,
        twilio_auth_token=None,
        twilio_from_number=None,
        twilio_messaging_service_sid=None,
        sms_default_country_code="+91",
        otp_expiry_seconds=300,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _spy(monkeypatch, settings):
    """Patch settings and both providers; return the list of (provider, to, ...) calls."""
    calls = []
    monkeypatch.setattr(sms_service, "get_settings", lambda: settings)
    monkeypatch.setattr(sms_service, "_send_via_twilio", lambda to, body: calls.append(("twilio", to, body)))

    async def fake_msg91(to, otp):
        calls.append(("msg91", to, otp))

    monkeypatch.setattr(sms_service, "_send_via_msg91", fake_msg91)
    return calls


def test_to_e164():
    assert sms_service._to_e164("9876543210", "+91") == "+919876543210"
    assert sms_service._to_e164("09876543210", "+91") == "+919876543210"
    assert sms_service._to_e164("+14155550100", "+91") == "+14155550100"


async def test_mock_fallback_when_unconfigured(monkeypatch):
    calls = _spy(monkeypatch, _settings())
    await sms_service.send_otp_sms("9876543210", "123456")
    assert calls == []


async def test_sends_via_twilio_when_only_twilio_configured(monkeypatch):
    calls = _spy(monkeypatch, _settings(**TWILIO))
    await sms_service.send_otp_sms("9876543210", "123456")
    assert len(calls) == 1
    provider, to, body = calls[0]
    assert (provider, to) == ("twilio", "+919876543210")
    assert "123456" in body


async def test_msg91_preferred_over_twilio_in_auto(monkeypatch):
    calls = _spy(monkeypatch, _settings(**TWILIO, **MSG91))
    await sms_service.send_otp_sms("9876543210", "123456")
    assert calls == [("msg91", "+919876543210", "123456")]


async def test_forced_provider_overrides_auto(monkeypatch):
    calls = _spy(monkeypatch, _settings(sms_provider="twilio", **TWILIO, **MSG91))
    await sms_service.send_otp_sms("9876543210", "123456")
    assert [c[0] for c in calls] == ["twilio"]

    calls = _spy(monkeypatch, _settings(sms_provider="mock", **TWILIO, **MSG91))
    await sms_service.send_otp_sms("9876543210", "123456")
    assert calls == []


async def test_provider_failure_does_not_raise(monkeypatch):
    monkeypatch.setattr(sms_service, "get_settings", lambda: _settings(**MSG91))

    async def boom(to, otp):
        raise RuntimeError("msg91 down")

    monkeypatch.setattr(sms_service, "_send_via_msg91", boom)
    await sms_service.send_otp_sms("9876543210", "123456")


async def test_msg91_request_shape(monkeypatch):
    monkeypatch.setattr(sms_service, "get_settings", lambda: _settings(**MSG91))
    seen = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"type": "success"}

    class FakeClient:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, url, params, headers, json):
            seen.update(url=url, params=params, headers=headers)
            return FakeResp()

    monkeypatch.setattr(sms_service.httpx, "AsyncClient", FakeClient)

    await sms_service._send_via_msg91("+919876543210", "123456")

    assert seen["url"] == sms_service.MSG91_OTP_URL
    assert seen["params"]["mobile"] == "919876543210"
    assert seen["params"]["otp"] == "123456"
    assert seen["params"]["template_id"] == "tmpl"
    assert seen["headers"]["authkey"] == "key"
