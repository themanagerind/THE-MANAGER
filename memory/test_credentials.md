# Test Credentials

## Demo Accounts (active)

| Role | Mobile | Password |
|------|--------|----------|
| Platform Owner | 9999999999 | owner123 |
| Admin | 8888888888 | admin123 |
| Sub-Admin | 7777777777 | subadmin123 |
| Resident (test) | 5555555550 | newpass123 |

## Auth Flow Notes
- All passwords set via bcrypt hash on user document.
- OTP delivery is currently MOCKED — `mock_otp` returned in API response and shown in UI as "Test Mode - OTP: XXXXXX".
- OTP signup flow: send-otp → verify-otp → register (status=pending) → admin approves → set password → login.
