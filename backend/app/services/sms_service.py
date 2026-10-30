"""
SMS gateway. Provider is picked from config, first match wins:

  1. MSG91   — MSG91_AUTH_KEY + MSG91_TEMPLATE_ID set (India; needs a
               DLT-approved OTP template)
  2. Twilio  — TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + a sender set
  3. mock    — logs the OTP, so local/dev/test works with no provider account,
               the same way PaymentMethod.MOCK_ONLINE mocks a real payment
               gateway.

Set SMS_PROVIDER to "msg91", "twilio" or "mock" to force one regardless of
what else is configured. This is the only place that knows how the SMS is
delivered; nothing in the OTP flow depends on it.

The OTP is logged only in the mock fallback, never returned from an API
response — that guarantee (otp_service.request_otp's docstring) still holds.
"""
import asyncio
import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger("app.sms")

MSG91_OTP_URL = "https://control.msg91.com/api/v5/otp"


def _to_e164(mobile: str, default_country_code: str) -> str:
    number = mobile.strip().replace(" ", "").replace("-", "")
    if number.startswith("+"):
        return number
    return f"{default_country_code}{number.lstrip('0')}"


def _twilio_configured(settings) -> bool:
    has_sender = settings.twilio_messaging_service_sid or settings.twilio_from_number
    return bool(settings.twilio_account_sid and settings.twilio_auth_token and has_sender)


def _msg91_configured(settings) -> bool:
    return bool(settings.msg91_auth_key and settings.msg91_template_id)


def _pick_provider(settings) -> str:
    forced = (settings.sms_provider or "auto").lower()
    if forced in ("msg91", "twilio", "mock"):
        return forced
    if _msg91_configured(settings):
        return "msg91"
    if _twilio_configured(settings):
        return "twilio"
    return "mock"


def _send_via_twilio(to: str, body: str) -> None:
    from twilio.rest import Client  # imported lazily: only needed when configured

    settings = get_settings()
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    params: dict = {"to": to, "body": body}
    if settings.twilio_messaging_service_sid:
        params["messaging_service_sid"] = settings.twilio_messaging_service_sid
    else:
        params["from_"] = settings.twilio_from_number
    client.messages.create(**params)


async def _send_via_msg91(to: str, otp: str) -> None:
    settings = get_settings()
    # MSG91 wants the number with country code and no "+", e.g. 919876543210.
    params = {
        "template_id": settings.msg91_template_id,
        "mobile": to.lstrip("+"),
        "otp": otp,  # our own OTP — MSG91 only delivers it, Redis still verifies it
        "otp_expiry": max(settings.otp_expiry_seconds // 60, 1),
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            MSG91_OTP_URL,
            params=params,
            headers={"authkey": settings.msg91_auth_key, "Content-Type": "application/json"},
            json={},
        )
    resp.raise_for_status()
    data = resp.json()
    if data.get("type") != "success":
        raise RuntimeError(f"MSG91 rejected the request: {data}")


async def send_otp_sms(mobile: str, otp: str) -> None:
    settings = get_settings()
    provider = _pick_provider(settings)
    if provider == "mock":
        logger.info("[MOCK SMS] OTP for %s: %s", mobile, otp)
        return

    to = _to_e164(mobile, settings.sms_default_country_code)
    try:
        if provider == "msg91":
            await _send_via_msg91(to, otp)
        else:
            body = (
                f"Your verification code is {otp}. It expires in "
                f"{max(settings.otp_expiry_seconds // 60, 1)} minutes. Do not share it with anyone."
            )
            # The Twilio SDK is blocking; keep it off the event loop.
            await asyncio.to_thread(_send_via_twilio, to, body)
    except Exception:
        # Never log the OTP or let a provider outage 500 the request; the user can retry.
        logger.exception("%s SMS send failed for %s", provider, to)
