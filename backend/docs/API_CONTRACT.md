# API Contract — Frozen v1

This is the frozen contract the frontend should build against. Breaking
changes after this point should be additive (new optional fields, new
endpoints) rather than altering existing request/response shapes, status
codes, or auth flow — see `docs/openapi_snapshot.json` for the exact,
diffable schema as of this freeze.

## Base URL / versioning

All endpoints are under `/api/v1`. A future breaking change would ship as
`/api/v2` rather than mutating `/api/v1` in place.

## Authentication

- **Header:** `Authorization: Bearer <access_token>` on every endpoint
  except `POST /auth/otp/request`, `POST /auth/otp/verify`,
  `POST /auth/select-account`, `POST /auth/token/refresh`,
  `POST /societies/signup`, `POST /residents/signup`, and `GET /health`.
- **Access token lifetime:** short (`jwt_access_token_expire_minutes`,
  default 30 min). **Refresh token lifetime:** long (`jwt_refresh_token_expire_days`,
  default 30 days), single-use — every `POST /auth/token/refresh` call
  rotates it (old one is immediately invalidated; reuse fails with 401,
  the standard replay-detection signal).
- **Logout:** `POST /auth/logout` with the refresh token revokes that
  session specifically.
- **Active role (dual-role, Section 4):** the access token carries
  `active_role` — a **hint**, never trusted alone. Every request re-derives
  current role/scope from the database (Section 49.14). Switch dashboards
  with `POST /auth/switch-role`, which reissues both tokens.

## Standard error response shape

```json
{ "detail": "human-readable message" }
```

- **Pydantic validation errors** (malformed request body) use FastAPI's
  default 422 shape: `{ "detail": [ { "loc": [...], "msg": "...", "type": "..." } ] }`.
- **Unhandled server errors** always return `500` with
  `{ "detail": "Internal server error" }` — never a stack trace (see
  `app/main.py`'s global exception handler).

## Status codes used, and what they mean

| Code | Meaning in this API |
|---|---|
| 200 | Success |
| 400 | Malformed/invalid request (e.g. missing proof for manual payment) |
| 401 | Missing/invalid/expired token, wrong OTP, revoked refresh token |
| 403 | Authenticated but not authorized (wrong role, outside Sub-admin scope) |
| 404 | Resource not found **in the caller's society** — cross-society existence is never confirmed or denied differently from "doesn't exist" |
| 409 | Conflict with current state (already approved, pending payment exists, insufficient wallet balance, duplicate vote target, etc.) |
| 422 | Request body failed schema validation |
| 429 | Rate-limited (OTP request cooldown/hourly cap, OTP lockout) |
| 500 | Unexpected server error |

## Status value vocabularies (frozen enums)

See `app/models/enums.py` — the single source of truth for every status/role
enum (`PaymentStatus`, `ProposalStatus`, `ExpenseBillStatus`, `VisitorStatus`,
etc.). The frontend should treat these as closed sets matching that file
exactly — do not add client-side handling for values that don't exist there.

## Pagination

**Standard shape:**

```
GET /payments?skip=0&limit=20
```

```json
{ "items": [...], "total": 137, "skip": 0, "limit": 20 }
```

`limit` is capped at 100, defaults to 20 (`app/schemas/pagination.py`).

**Now applied to:** `GET /payments`, `GET /notices`, `GET /account-entries`,
`GET /proposals`, `GET /expense-bills`, `GET /manager-todos`,
`GET /visitors/mine`, `GET /amenities/bookings`.

**Intentionally NOT yet paginated** — `GET /complaints`: the Sub-admin-scope
filter (`filter_by_subadmin_scope`) runs in Python *after* the DB fetch, so
naively paginating the DB query first would produce an incorrect `total`
and could return fewer than `limit` items for a Sub-admin even when more
exist. Fixing this properly means pushing the scope filter into the SQL
query itself (join through `properties`/`sub_admin_scopes`) rather than
just adding `?skip=&limit=` — deferred as its own follow-up rather than
shipping a paginated response with a misleading `total`. `GET /visitors/guard-view`
is similarly deferred (small, security-sensitive dataset; not yet a
priority). Both remain full unpaginated lists for now — build against that
shape for these two endpoints specifically.

## Filtering

No generic filter query-language exists. Where filtering matters today it's
role-implicit (e.g. a Resident's `GET /complaints` returns only their own;
a Sub-admin's returns only their scope) rather than a query parameter.
Explicit filter params (by status, date range, category) are not yet
implemented — treat as a planned addition, not a current capability.

## Idempotency

`POST /payments` requires a client-generated `idempotency_key` (UUID) —
required for the offline background-sync case (Section 37) but safe to
always send. Retrying with the same key against the same
`maintenance_due_id` returns `409`, never a duplicate payment.

## Source of truth

`docs/openapi_snapshot.json` is the literal, machine-readable frozen
contract (generated from the live FastAPI app — see the command in
`docs/MIGRATION_VERIFICATION.md`'s sibling note below). Regenerate it
whenever the contract intentionally changes, and diff it in review to
catch accidental breaking changes.

```bash
python -c "
from app.main import app
import json
json.dump(app.openapi(), open('docs/openapi_snapshot.json', 'w'), indent=2)
"
```
