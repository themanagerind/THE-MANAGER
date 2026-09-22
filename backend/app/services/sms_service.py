"""
Mock SMS gateway. A real deployment sends the OTP via a provider (MSG91,
Twilio, etc.) — none has been chosen yet, so send_otp_sms() logs instead,
the same way PaymentMethod.MOCK_ONLINE mocks a real payment gateway. This
is the only place that needs to change once a provider is picked; nothing
in the OTP flow itself depends on how the SMS is actually delivered.

The OTP is logged, never returned from an API response — that guarantee
(otp_service.request_otp's docstring) still holds; this is server-side
visibility for local/dev/test only.
"""
import logging

logger = logging.getLogger("app.sms")


async def send_otp_sms(mobile: str, otp: str) -> None:
    """MOCK — logs the OTP instead of sending a real SMS."""
    logger.info("[MOCK SMS] OTP for %s: %s", mobile, otp)
