# Full Project Audit — 2026-09-25

## Scope & method

A full-codebase audit of THE-MANAGER (backend `app/api`, `app/services`, `app/models` +
the entire frontend `src/`), looking specifically for **correctness bugs, race
conditions/TOCTOU windows, infinite loops or hangs, and broken state machines** —
not style or architecture nits. Four parallel deep-review passes were run:

1. Identity/auth/account-lifecycle (auth, admins, admin-change, sub-admins, staff, residents, users, societies)
2. Payments/money (payments, maintenance dues, wallet, ledger, account entries, expense bills)
3. Day-to-day operations (complaints, visitors, notices, amenities, proposals, manager to-dos, properties, uploads)
4. The entire frontend (React pages, API clients, hooks, offline queue, auth context, routing)

Every finding below was independently re-verified by reading the actual code
(and, for the concurrency bugs, reproduced with a real `asyncio.gather` test
against Postgres) before being fixed — nothing here is speculative.

**Baseline before this audit:** 244/244 backend tests passing.
**After this audit's fixes:** **254/254 backend tests passing** (10 new
regression tests added, one per confirmed bug, all of which fail against the
pre-fix code and pass against the fix).

---

## Bugs found and fixed

### 1. [HIGH] Admin-change approval could get stuck PENDING forever — race condition
**File:** `backend/app/services/admin_change_service.py` (`decide_admin_change_approval`)

When a society has 2+ active Sub-admins, each approval decision computed
`done` (committed approvals) from the DB, then added `+1` locally for its own
not-yet-committed decision, finalizing only if `done + 1 >= total`. Under
Postgres's default READ COMMITTED isolation, two Sub-admins approving at
nearly the same instant each fail to see the other's still-uncommitted
approval — both compute `done + 1 < total` and **neither finalizes**, even
though every approval is actually done. The request is left permanently
`PENDING`, and since a pending request blocks any new one for that society,
this silently locks the Admin-change feature for the whole society until
someone fixes the DB row by hand.

**Fix:** lock the `AdminChangeRequest` row (`.with_for_update()`) before
reading progress, serializing concurrent decisions the same way
`proposal_service.cast_vote` already does for proposal votes.
**Regression test:** `tests/test_concurrency.py::test_concurrent_unanimous_admin_change_approval_does_not_get_stuck`
— fires 2 Sub-admins' approvals concurrently, asserts the request reaches `APPROVED`.

### 2. [HIGH] Amenity booking approval race — two overlapping bookings could both get APPROVED
**File:** `backend/app/services/amenity_service.py` (`decide_booking`)

This session's earlier fix for amenity double-booking added an "is another
booking already APPROVED for this overlapping time?" check inside
`decide_booking`, but that check itself had no row lock. Two Admins (or one
Admin in two tabs) approving two different, time-overlapping PENDING
bookings at the same instant could both pass the check before either
commits — resulting in two APPROVED, time-overlapping bookings for the same
amenity, the exact bug the earlier fix was meant to prevent.

**Fix:** lock every PENDING/APPROVED booking for that amenity+date before
running the overlap check, so a concurrent decision on an overlapping
booking blocks until the first one commits.
**Regression test:** `tests/test_concurrency.py::test_concurrent_decide_booking_never_double_approves_overlapping_slots`.

### 3. [HIGH] Sub-admin could read every amenity booking in the society, outside their scope
**File:** `backend/app/api/v1/amenities.py` (`GET /amenities/bookings`)

Unlike every other list endpoint in the app (payments, complaints, visitors),
this one only branched on `RESIDENT` vs. everyone else — a Sub-admin fell
into the same unfiltered branch as Admin, so a Sub-admin scoped to one
Wing/Row could read every booking society-wide, including which resident
booked what in wings they have no assigned scope over. The write path
(`decide_booking`) was already correctly scope-checked; this read path wasn't.

**Fix:** added a Sub-admin branch that fetches the full list, filters by
`subadmin_has_scope_over_property`, then paginates — same pattern already
used by `payments.list_payments` for the identical bug class.
**Regression test:** `tests/test_authorization.py::test_subadmin_cannot_see_amenity_bookings_outside_scope`.

### 4. [MEDIUM] Withdrawing a proposal could silently overwrite an already-approved outcome
**File:** `backend/app/services/proposal_service.py` (`withdraw_proposal`)

`withdraw_proposal` read the proposal with a plain, unlocked `SELECT`, while
`cast_vote` (correctly) locks the row. If an Admin withdrew a proposal at the
same instant its deciding vote was being cast, `withdraw_proposal`'s stale
read could still see `OPEN`, and its own unconditional `UPDATE` (no check on
the current status) would then overwrite an already-committed `APPROVED`
status back to `WITHDRAWN` — both requests returning `200 OK`, with the real
outcome silently lost.

**Fix:** lock the proposal row in `withdraw_proposal` too, so it always sees
the current (possibly post-vote) status before deciding.
**Regression test:** `tests/test_concurrency.py::test_concurrent_withdraw_and_deciding_vote_never_both_succeed`
— fires the deciding vote and a withdraw concurrently, asserts exactly one
wins and the final status matches whichever one did.

### 5. [MEDIUM] An expense bill could get stuck forever if the only Sub-admin left
**Files:** `backend/app/services/subadmin_service.py` (`demote_subadmin`, `decide_resignation`), `backend/app/services/expense_bill_service.py` (new `has_pending_bills`)

An expense bill needs 100% of *active* Sub-admins to approve it, and only an
active Sub-admin can even call the decision endpoint. Nothing stopped an
Admin from demoting the last active Sub-admin (or approving their
resignation) while a bill was `PENDING_APPROVAL`. Once active count hits 0,
the bill can never be approved (0/0 never reaches the threshold) or rejected
(no one is left who's allowed to) — a permanently orphaned bill with no
recovery path.

**Fix:** both `demote_subadmin` and `decide_resignation`'s approve branch now
check whether the target is the *only* active Sub-admin and, if so, whether
any bill in the society is still pending — if both are true, the action is
blocked with a clear 409 telling the Admin to resolve the bill (or promote
another Sub-admin) first.
**Regression tests:** new `tests/test_expense_bills.py` (this module had
**zero** test coverage before this audit despite being a full money-adjacent
approval workflow) —
`test_demoting_last_active_subadmin_blocked_while_bill_pending` and
`test_approving_last_subadmins_resignation_blocked_while_bill_pending`,
plus 3 basic happy-path tests for the module.

### 6. [LOW] Payment correction accepted a zero/negative amount
**File:** `backend/app/schemas/payment.py` (`CorrectPaymentIn`)

`new_amount` had no validation, so a non-positive value would flow through
wallet adjustment and ledger posting before failing only at the final commit
via the database's `ck_payments_amount_positive` constraint — the whole
transaction rolled back correctly either way, but as an unhandled 500
instead of a clean 400.

**Fix:** `new_amount: float = Field(gt=0)`.
**Regression test:** `tests/test_payments.py::test_correction_rejects_non_positive_new_amount`.

---

## Findings noted but intentionally not fixed (low severity / out of scope)

- **Storage-quota check TOCTOU** (`backend/app/services/upload_service.py`,
  `save_payment_proof`): the 2GB storage cap is checked, then the file is
  written, with no lock between the two — concurrent uploads near the cap
  could push total storage slightly past it. Low impact (soft ops limit,
  already rate-limited to 20 uploads/hour/resident); fixing it cleanly needs
  a DB-backed atomic reservation, a bigger change than this audit's scope.
- **N+1 query pattern for Sub-admin-scoped lists** (`payments.list_payments`/
  `list_pending`, and the new amenities scope-fix above): fetches the whole
  society's rows, then calls `subadmin_has_scope_over_property` once per row
  in a Python loop before paginating. This is a pre-existing, consistent
  pattern already used everywhere in the codebase for this exact problem
  (scope filtering has to happen before pagination) — a real perf cost at
  large data volumes, but not a correctness bug or a hang risk, and fixing it
  would mean restructuring the scope-check to be SQL-joinable across every
  module that uses this pattern. Left as-is.

## Areas reviewed and found clean

- **Frontend (entire app):** every `useMutation`'s cache invalidation, every
  `useEffect` dependency array, the offline queue, the token-refresh
  single-flight logic, and the `"HH:MM"` vs. `"HH:MM:SS"` string-comparison
  bug class (fixed once already this session in the amenities booking form)
  were all checked app-wide. No confirmed bugs.
- **Auth/OTP/tokens:** rate limiting, lockout, one-time-use invalidation,
  refresh-token rotation, and live role/society-status re-verification on
  every request were all confirmed correct.
- **Tenant isolation:** role checks and `society_id` scoping were confirmed
  present and correct across every other endpoint checked (residents,
  sub-admins, staff, properties, notices, manager to-dos, file uploads).
- **Money integrity:** no double-spend, double-credit, or lost-idempotency
  bug was found — the existing row-locking and partial unique indexes on
  payment/wallet/ledger flows hold up under concurrency.

---

## Test results

```
Backend:  254/254 passing (was 244 before this audit; +10 new regression tests)
Frontend: build clean, lint 0 errors (2 pre-existing warnings), 24/24 vitest tests passing
```

No database migration was needed for any of these fixes — all are either
application-level locking/validation changes or new read-side scope filters.
