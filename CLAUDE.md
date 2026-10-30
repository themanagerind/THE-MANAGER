# CLAUDE.md — Housing Society Management Platform

This file gives Claude Code the context it needs to work on this repository.
Place it in the **root of the project** (the folder that contains both `backend/` and `frontend/`).

> Folder names and commands below follow the standard layout for this stack.
> If your repo uses different paths or scripts, edit the sections marked **(verify)**.

---

## 1. What this project is

A multi-role housing society management platform:

- **Backend:** FastAPI REST API (endpoint count drifts as modules are added — check
  `app.openapi()`'s path count rather than a number here, which goes stale)
- **Frontend:** React PWA (installable, offline-capable)
- **Status:** Backend is mature and covers every module. Frontend has caught up —
  every role's dashboard (Resident, Admin, Sub-admin, Manager, Guard, Platform
  Owner) is wired to its backend API; `PlaceholderPage` is only used for the
  catch-all 404 route now. Current gaps are narrower: individual features whose
  backend API shipped with no frontend UI yet (wallet-redemption was the last
  one found this way — closed; see Section 7 for how to re-check) and i18n
  page-content translation beyond the dashboard chrome (nav/common labels).

### User roles
| Role | Purpose |
|---|---|
| Platform Admin | Manages the whole platform / all societies |
| Admin | Society-level administrator |
| Sub-admin | Delegated admin with limited permissions |
| Manager | Society manager — handles tasks, staff, day-to-day operations |
| Guard | Gate security — visitor entry/exit |
| Resident | Flat owner / tenant |

Every feature change must respect role-based access on **both** the API (authorization checks)
and the UI (role-based routing/menus).

---

## 2. Tech stack

### Backend
- Python + **FastAPI**
- **PostgreSQL** database
- **Alembic** for schema migrations
- **Redis** (rate limiting / caching)
- **JWT** authentication
- Security hardening: OWASP compliance, rate limiting, audit logging (**payments only** — see rule 3 below, don't trust this line either without re-checking)
- **Docker** deployment
- Test suite: **the full `pytest` suite must stay passing** (grows as coverage is added — check `pytest -q`'s own count rather than a number here, which goes stale)

### Frontend
- **React 18.3** + **TypeScript** + **Vite**
- **Tailwind CSS**
- **React Query** (server state) + **React Router** (routing)
- **PWA:** service worker, offline support, installable
- **Offline queue** — requests made while offline are stored and synced when back online
- Unit tests with **Vitest**

---

## 3. API modules

| Module | Covers |
|---|---|
| Authentication | Login, token refresh, logout, password flows (JWT) |
| Residents | Resident profiles, onboarding, flat mapping |
| Properties | Societies, buildings/wings, flats |
| Payments | Maintenance dues, payment records, receipts |
| Expense bills | Society expenses and bills |
| Complaints | Raise, assign, track, resolve complaints |
| Visitors | Visitor entry/exit logs (Guard workflow), approvals |
| Amenities | Amenity listing and bookings |
| Notices | Society notices / announcements |
| Proposals | Proposals raised for society decisions |
| Manager tasks | Tasks assigned to/by the manager |
| Staff | Society staff records |
| Sub-admins | Creating and managing sub-admins and their permissions |
| Accounts | Society accounts / ledger |

Full endpoint documentation: `HOUSING_BACKEND_COMPLETE_API_REFERENCE.md`

---

## 4. Repository layout (verify)

```
/
├── CLAUDE.md
├── backend/
│   ├── app/              # FastAPI app: routers, models, schemas, services, core (config, security)
│   ├── alembic/          # Migration scripts
│   ├── tests/            # pytest suite
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/              # React + TS source (pages, components, hooks, api, offline queue)
│   ├── public/           # PWA manifest, icons
│   ├── vite.config.ts
│   └── package.json
├── docker-compose.yml
└── docs/                 # Phase 5 documents (see section 8)
```

---

## 5. Common commands (verify)

### Backend
```bash
cd backend
pip install -r requirements.txt
alembic upgrade head                 # apply migrations
uvicorn app.main:app --reload        # run dev server
pytest                               # run all tests
alembic revision --autogenerate -m "describe change"   # new migration
```

### Frontend
```bash
cd frontend
npm install
npm run dev          # Vite dev server
npm run build        # production build (includes service worker)
npm run test         # Vitest
npm run lint         # if configured
```

### Docker
```bash
docker compose up --build                  # local dev infra (Postgres + Redis only)
docker compose -f docker-compose.prod.yml up -d --build   # reference prod topology — see Section 8
```

---

## 6. Rules for working in this repo

1. **Never break the test suite.** Run `pytest` after any backend change and `npm run test` after frontend changes. Don't mark work done while tests fail.
2. **Every schema change needs an Alembic migration.** Never edit the database by hand or modify old migrations that may already be applied in production.
3. **Security is non-negotiable:**
   - Every new endpoint needs JWT auth + a role/permission check (unless it's explicitly public, like login).
   - Keep rate limiting on sensitive actions (auth, payments, accounts, sub-admin permission changes). As of 2026-10-20's audit this was only true for auth (OTP/signup) plus society search and uploads (`grep -rln "HTTP_429" app/` showed exactly those 5 files) — payments, accounts, and sub-admin permission changes had none, despite this rule naming them explicitly. Being fixed via `app/core/rate_limit.py` (a shared helper, factored out of the duplicated otp/signup/search/upload pattern) wired into `submit_payment`, `create_manual_entry`, and the sub-admin promote/demote/scope endpoints. Re-check with the same grep before trusting this is still current.
   - **"Audit logging" is real, but payments-only.** `PaymentAuditLog` (`app/models/payments.py`) is a genuine, immutable (INSERT/SELECT only) trail of CREATED/PAID_MARKED/APPROVED/REJECTED/CORRECTED for every payment — correctly written to from `payment_service/{submission,approval,rejection,correction}.py`. A 2026-10-20 audit pass initially missed this (grepped for the literal string `AuditLog`, which doesn't match `PaymentAuditLog`) and claimed no audit logging existed at all anywhere — that was wrong; verify by grepping `class.*AuditLog` before trusting either claim. What's still actually true: there is **no equivalent for accounts, sub-admin permission changes, or auth** — those sensitive actions (named in this same rule) leave no audit trail, only incidental `*_reason` fields on a few domain rows (e.g. `AdminChangeRequest.decision_reason`) for their own terminal decision, and a denied/attempted action (every 403) leaves no trace anywhere. Don't assume a new sensitive action outside payments gets logged for free.
   - Validate all input with Pydantic schemas; never build raw SQL from user input.
   - Never commit secrets. Config comes from environment variables.
4. **Keep API and UI in sync.** When an endpoint changes, update the frontend API client/types, and update `HOUSING_BACKEND_COMPLETE_API_REFERENCE.md`.
5. **Respect the offline queue.** Any new write action in the frontend should go through the existing offline-queue mechanism so it syncs when the device is back online. Don't bypass it with direct fetch calls.
6. **Role-based UI.** New pages/menus must be gated by role, matching the backend permissions.
7. **Production-readiness phase:** prefer small, reviewable changes. Avoid large refactors or dependency upgrades unless asked.
8. Use TypeScript strictly on the frontend (no `any` without reason); use type hints on the backend.

---

## 7. Current phase — Phase 5 Production Readiness

- **Week 1:** the planning docs this section used to describe as "✅ Complete" (`WEEK_2_START_HERE.md`, `WEEK_2_GATE_0_EXECUTION_GUIDE.md`, `GATE_0_EXECUTION_WORKSHEET.md`, `PHASE_5_COMPLETE_EXECUTION_PLAYBOOK.md`, `PHASE_5_FINAL_DELIVERY_SUMMARY.md`) do not actually exist in this repo — confirmed by `ls *.md` at the repo root, not just a stale claim like the old "frontend incomplete" one in Section 1 used to be. Don't trust this line either; re-check with `ls` before relying on it.
- **Deployable artifacts now exist:** `backend/Dockerfile`, `frontend/Dockerfile` + `frontend/nginx.conf`, and `docker-compose.prod.yml` (repo root, with `.env.prod.example`) — none of these existed before despite Section 2/Section 4 referencing Docker deployment. They were written and the pip-install/build/test steps verified from this environment, but never `docker build`/`docker run`-tested end-to-end (no Docker daemon available in that sandbox) — do that once before relying on them for a real deploy.
- **Week 2 (Gates 0–4, infrastructure verification + testing gates) has NOT been executed.** It needs real production hosting/DNS/TLS/load-balancer access that no coding session has — this has to be done by whoever holds that infrastructure, not assumed complete.
- **Week 3** (stakeholder sign-offs, production deployment, 24-hour monitoring) hasn't started.

### Gate 0 — Infrastructure inventory verification (90–120 min), still to do
1. Hosting provider verification
2. PostgreSQL operational check
3. Redis operational check
4. Load balancer configuration
5. DNS resolution verification
6. TLS certificate validation
7. End-to-end accessibility test

No worksheet exists to track this yet — create one (or reuse this section) when someone with real infra access actually runs it.

### Current engineering priority: close the remaining backend-ahead-of-frontend gaps

Every role's dashboard now routes to a real page (no `PlaceholderPage`
left outside the 404 catch-all) — the frontend-wide rebuild described
here in earlier revisions of this file is done. What's left is narrower:
individual backend features that shipped without frontend UI, found by
checking whether an API module has a matching `frontend/src/api/*.ts`
client and a page that calls it (wallet redemption was the last one
found this way — closed; re-check periodically rather than trusting a
list here, which goes stale the moment the next gap is closed).

When building one of these, follow the same pattern Resident's built-out
pages (Complaints, Dues, Amenities, etc.) already use: list → detail/
create modal → mutation, `Page[T]` for paginated endpoints, `Table`/
`Badge`/`Modal`/`Button` from `components/`.

---

## 8. Key documents

| File | Purpose |
|---|---|
| `HOUSING_BACKEND_COMPLETE_API_REFERENCE.md` | Full endpoint documentation — generated from `app.openapi()`, run `python -m scripts.generate_api_reference` from `backend/` after any endpoint change (see rule 4 above) |
| `docker-compose.prod.yml` + `.env.prod.example` | Reference production deployment topology (Postgres + Redis + `backend/Dockerfile` + `frontend/Dockerfile`/`nginx.conf`) |
| `backend/requirements.lock.txt` | Full exact dependency pin (direct + transitive) — what `backend/Dockerfile` actually installs from, so a production image build is reproducible. `requirements.txt` stays the human-edited, unpinned (`>=`) list for local dev; regenerate the lock file (see its own header) and run the full suite against it after changing `requirements.txt`, before committing either |
| `AUDIT_REPORT_2026-09-25.md` | Past security/correctness audit findings |

The `WEEK_2_*`/`PHASE_5_*`/`GATE_0_*` planning docs this table used to list don't exist in this repo (see Section 7) — don't point anyone at a file name from here without confirming it's actually present.

---

## 9. How to ask Claude for help here

- Be specific: name the module, role and endpoint (e.g. "Add a `cancel booking` endpoint to Amenities for Residents").
- Ask for tests alongside code changes.
- If something is uncertain (config, infra, credentials), Claude should say so and ask rather than guess.
