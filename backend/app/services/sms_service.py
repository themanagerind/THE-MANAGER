"""
SMS gateway. Sends the OTP through Twilio when credentials are configured
(TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + a sender); otherwise falls back to
logging it, so local/dev/test works with no provider account — the same way
PaymentMethod.MOCK_ONLINE mocks a real payment gateway. This is the only
place that knows how the SMS is delivered; nothing in the OTP flow depends
on it.

The OTP is logged only in the mock fallback, never returned from an API
response — that guarantee (otp_service.request_otp's docstring) still holds.
"""
import asyncio
import logging

from app.core.config import get_settings

logger = logging.getLogger("app.sms")


def _to_e164(mobile: str, default_country_code: str) -> str:
    number = mobile.strip().replace(" ", "").replace("-", "")
    if number.startswith("+"):
        return number
    return f"{default_country_code}{number.lstrip('0')}"


def _send_via_twilio(to: str, body: str) -> None:
    from twilio.rest import Client  # imported lazily: only needed when configured

    settings = get_settings()
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    params: dict = {"to": to, "body": body}
    if settings.twilio_messaging_service_sid:
        params["messaging_service_sid"] = settings.twilio_messaging_service_sid
    else:
<<<<<<< HEAD
        params["from_"] = settings.twilio_from_number or settings.twilio_phone_number
=======
        params["from_"] = settings.twilio_from_number
>>>>>>> 191853d0b99367296d07aeb3fd7615459bc0b889
    client.messages.create(**params)


async def send_otp_sms(mobile: str, otp: str) -> None:
    settings = get_settings()
<<<<<<< HEAD
    from_number = settings.twilio_from_number or settings.twilio_phone_number
    has_sender = settings.twilio_messaging_service_sid or from_number
=======
    has_sender = settings.twilio_messaging_service_sid or settings.twilio_from_number
>>>>>>> 191853d0b99367296d07aeb3fd7615459bc0b889
    if not (settings.twilio_account_sid and settings.twilio_auth_token and has_sender):
        logger.info("[MOCK SMS] OTP for %s: %s", mobile, otp)
        return

    to = _to_e164(mobile, settings.sms_default_country_code)
    body = (
        f"Your verification code is {otp}. It expires in "
        f"{max(settings.otp_expiry_seconds // 60, 1)} minutes. Do not share it with anyone."
    )
    try:
        # The Twilio SDK is blocking; keep it off the event loop.
        await asyncio.to_thread(_send_via_twilio, to, body)
<<<<<<< HEAD
    except Exception as exc:
        # Never log the OTP or let a provider outage 500 the request; the user can retry.
        logger.exception("Twilio SMS send failed for %s: %s", to, exc)
=======
    except Exception:
        # Never log the OTP or let a provider outage 500 the request; the user can retry.
        logger.exception("Twilio SMS send failed for %s", to)
>>>>>>> 191853d0b99367296d07aeb3fd7615459bc0b889
