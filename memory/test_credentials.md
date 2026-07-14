# Test Credentials

## Demo Accounts (preview DB status — June 2026)

| Role | Mobile | Password | Status |
|------|--------|----------|--------|
| Platform Owner | 9999999999 | owner123 | WORKS (auto-seeded on startup) |
| Admin | 8888888888 | admin123 | WORKS (society "Test Society", Wing A, 4 flats, 4 bills 2026-06 created by testing agent) |
| Sub-Admin | 7777777777 | subadmin123 | NOT SEEDED in current preview DB (401) — create via admin promote flow if needed |
| Resident (test) | 5555555550 | newpass123 | NOT VERIFIED in current preview DB — create via OTP registration flow if needed |

## Auth Flow Notes
- All passwords set via bcrypt hash on user document.
- OTP delivery is currently MOCKED — `mock_otp` returned in API response and shown in UI as "Test Mode - OTP: XXXXXX".
- OTP signup flow: send-otp → verify-otp → register (status=pending) → admin approves → set password → login.
- Only Platform Owner is auto-seeded on startup (server.py). Other accounts must be created via UI/API.
