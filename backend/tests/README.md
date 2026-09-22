# Running the test suite

These tests exercise **real** PostgreSQL constraints (composite FKs, partial
unique indexes, row locking via `SELECT ... FOR UPDATE`) and Redis (OTP
hashing, rate limits, lockout, refresh-token rotation). They intentionally do
**not** run against SQLite or a mocked session — those would silently pass
tests that a real production database would reject.

## Setup

```bash
pip install -r requirements.txt -r requirements-dev.txt

# Point at disposable test instances (never your dev/prod DB):
export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/housing_test"
export TEST_REDIS_URL="redis://localhost:6379/15"   # a scratch Redis DB index

createdb housing_test   # if it doesn't exist yet
```

## Run

```bash
pytest tests/ -v
```

Each test session creates the full schema fresh (via `Base.metadata.create_all`,
not Alembic — faster for iteration) and drops it afterward. Redis DB 15 is
flushed before and after every individual test.

## What's covered (priority order per FINAL PROMPT Section 42)

1. **`test_auth.py`** — OTP request/verify, hashing (never plaintext in
   Redis), request rate-limiting, verify-attempt lockout, dual-role
   switching, stale-JWT-after-revocation rejection.
2. **`test_authorization.py`** — cross-society isolation: an Admin can't see
   or act on another society's properties/residents; Sub-admin scope checks
   reject out-of-scope and cross-society properties even with a
   well-formed, legitimately-authenticated request.
3. **`test_payments.py`** — the full payment → wallet → ledger chain,
   exactly-once crediting, proof-required enforcement, one-pending-per-due,
   idempotency-key dedupe, and the correction event model (adjustment, not
   a second payment).
4. **`test_concurrency.py`** — concurrent duplicate-approve requests
   (`asyncio.gather`) resolve to exactly one success and one wallet credit;
   concurrent proposal votes all land without any lost updates.

## What's intentionally NOT here yet

Full coverage of every endpoint (visitors, complaints, amenities, notices,
expense bills, account entries) — the four files above cover the
**highest-risk** surfaces first, per the explicit priority order requested.
Extending coverage to the remaining modules is the natural next increment,
following the same fixtures in `conftest.py`.
