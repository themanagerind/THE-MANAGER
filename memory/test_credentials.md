# Test Credentials — Housing Society Management Platform

Auth is **OTP-based** (mobile number → 6-digit OTP). SMS is MOCKED — the OTP is
not sent by SMS. To obtain an OTP for testing, generate it via the backend's
own service (it returns the plaintext OTP), because it is stored HASHED in Redis:

```bash
cd /app/backend && redis-cli --scan --pattern 'otp:*' | xargs -r redis-cli del
/root/.venv/bin/python -c "import asyncio; from app.services.otp_service import request_otp; print(asyncio.run(request_otp('9999999999')))"
```

Then POST the printed OTP to `/api/v1/auth/otp/verify` with the mobile.

## Seeded account
| Role | Mobile | Notes |
|---|---|---|
| Platform Owner | 9999999999 | Seeded via `python -m scripts.seed_platform_owner` |

Create more accounts through the app's Signup / admin flows.
