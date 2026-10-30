from types import SimpleNamespace

from app.services import sms_service


def _settings(**overrides):
    base = dict(
        twilio_account_sid=None,
        twilio_auth_token=None,
        twilio_from_number=None,
        twilio_messaging_service_sid=None,
        sms_default_country_code="+91",
        otp_expiry_seconds=300,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_to_e164():
    assert sms_service._to_e164("9876543210", "+91") == "+919876543210"
    assert sms_service._to_e164("09876543210", "+91") == "+919876543210"
    assert sms_service._to_e164("+14155550100", "+91") == "+14155550100"


async def test_mock_fallback_when_unconfigured(monkeypatch):
    monkeypatch.setattr(sms_service, "get_settings", lambda: _settings())
    called = []
    monkeypatch.setattr(sms_service, "_send_via_twilio", lambda *a: called.append(a))

    await sms_service.send_otp_sms("9876543210", "123456")

    assert called == []


async def test_sends_via_twilio_when_configured(monkeypatch):
    monkeypatch.setattr(
        sms_service,
        "get_settings",
        lambda: _settings(
            twilio_account_sid="ACxxx", twilio_auth_token="tok", twilio_from_number="+10000000000"
        ),
    )
    called = []
    monkeypatch.setattr(sms_service, "_send_via_twilio", lambda to, body: called.append((to, body)))

    await sms_service.send_otp_sms("9876543210", "123456")

    assert len(called) == 1
    to, body = called[0]
    assert to == "+919876543210"
    assert "123456" in body


async def test_provider_failure_does_not_raise(monkeypatch):
    monkeypatch.setattr(
        sms_service,
        "get_settings",
        lambda: _settings(
            twilio_account_sid="ACxxx", twilio_auth_token="tok", twilio_messaging_service_sid="MGxxx"
        ),
    )

    def boom(to, body):
        raise RuntimeError("twilio down")

    monkeypatch.setattr(sms_service, "_send_via_twilio", boom)

    await sms_service.send_otp_sms("9876543210", "123456")
