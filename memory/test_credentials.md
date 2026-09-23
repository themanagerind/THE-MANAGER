# Test Credentials — Housing Society Management Platform

Auth is **OTP-based** (mobile number → 6-digit OTP). SMS is MOCKED. In
**development** the OTP is now returned by `POST /api/v1/auth/otp/request` as
`dev_otp` and shown/auto-filled on the Login screen (yellow "Dev mode" banner),
so login is completable without a real SMS gateway. In production
(environment != "development") `dev_otp` is never populated.

To log in as Platform Owner: open the app → enter mobile **9999999999** →
"Send code" → the 6-digit code appears on screen (auto-filled) → "Verify &
continue" → logged in as PLATFORM_OWNER.

## Seeded account
| Role | Mobile | Notes |
|---|---|---|
| Platform Owner | 9999999999 | Seeded via `python -m scripts.seed_platform_owner` |

Create more accounts through the app's Signup / admin flows.
