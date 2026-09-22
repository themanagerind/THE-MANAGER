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
- **Status:** Backend is mature and covers every module. Frontend is behind it —
  Resident is essentially complete; Admin has several `PlaceholderPage` routes still
  (Complaints, Visitors, Notices, Amenities, Proposals, Expense Bills, Accounts);
  Sub-admin, Guard, and most of Platform Owner are still placeholders too. Closing
  that gap (wiring each placeholder to its already-built backend API) is the
  current priority — see the note at the end of Section 7.

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
- Security hardening: OWASP compliance, rate limiting, audit logging
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
docker compose up --build
```

---

## 6. Rules for working in this repo

1. **Never break the test suite.** Run `pytest` after any backend change and `npm run test` after frontend changes. Don't mark work done while tests fail.
2. **Every schema change needs an Alembic migration.** Never edit the database by hand or modify old migrations that may already be applied in production.
3. **Security is non-negotiable:**
   - Every new endpoint needs JWT auth + a role/permission check (unless it's explicitly public, like login).
   - Keep rate limiting and audit logging on sensitive actions (auth, payments, accounts, sub-admin permission changes).
   - Validate all input with Pydantic schemas; never build raw SQL from user input.
   - Never commit secrets. Config comes from environment variables.
4. **Keep API and UI in sync.** When an endpoint changes, update the frontend API client/types, and update `HOUSING_BACKEND_COMPLETE_API_REFERENCE.md`.
5. **Respect the offline queue.** Any new write action in the frontend should go through the existing offline-queue mechanism so it syncs when the device is back online. Don't bypass it with direct fetch calls.
6. **Role-based UI.** New pages/menus must be gated by role, matching the backend permissions.
7. **Production-readiness phase:** prefer small, reviewable changes. Avoid large refactors or dependency upgrades unless asked.
8. Use TypeScript strictly on the frontend (no `any` without reason); use type hints on the backend.

---

## 7. Current phase — Phase 5 Production Readiness

- **Week 1:** ✅ Complete — specifications, procedures and documentation ready
- **Week 2:** Infrastructure verification + testing gates (Gates 0–4, ~6–9 hours total, can be split across 7 days)
- **Week 3:** Stakeholder sign-offs, production deployment, 24-hour monitoring

### Next immediate task: Gate 0 — Infrastructure inventory verification (90–120 min)
1. Hosting provider verification
2. PostgreSQL operational check
3. Redis operational check
4. Load balancer configuration
5. DNS resolution verification
6. TLS certificate validation
7. End-to-end accessibility test

Track progress in `GATE_0_EXECUTION_WORKSHEET.md`.

### Current engineering priority: finish the frontend

The backend covers every module; the frontend doesn't yet call all of it.
Still `PlaceholderPage`, each with a working backend API already sitting
idle behind it:

- **Admin:** Complaints, Visitors, Notices, Amenities, Proposals, Expense
  Bills, Accounts
- **Sub-admin:** almost everything (Overview, Dues, Complaints, Proposals,
  Expense Bills)
- **Security Guard:** Visitors (gate entry/exit)
- **Platform Owner:** mostly done (Societies page is now real) — nothing
  else exists yet for this role beyond Societies

Resident is essentially complete and is the reference pattern for how a
module should look (list → detail/create modal → mutation, `Page[T]` for
paginated endpoints, `Table`/`Badge`/`Modal`/`Button` from `components/`).
Build the remaining ones the same way, one module at a time.

---

## 8. Key documents

| File | Purpose |
|---|---|
| `WEEK_2_START_HERE.md` | Quick reference guide for Week 2 |
| `WEEK_2_GATE_0_EXECUTION_GUIDE.md` | Detailed Gate 0 infrastructure verification procedure |
| `GATE_0_EXECUTION_WORKSHEET.md` | Live tracking sheet for the 7 infrastructure checks |
| `HOUSING_BACKEND_COMPLETE_API_REFERENCE.md` | Full endpoint documentation (not yet in this repo — generate from `app.openapi()` when needed) |
| `PHASE_5_COMPLETE_EXECUTION_PLAYBOOK.md` | Complete Week 2–3 strategy with decision trees |
| `PHASE_5_FINAL_DELIVERY_SUMMARY.md` | Week 1 completion summary |

Read the relevant document before starting gate or deployment work.

---

## 9. How to ask Claude for help here

- Be specific: name the module, role and endpoint (e.g. "Add a `cancel booking` endpoint to Amenities for Residents").
- Ask for tests alongside code changes.
- If something is uncertain (config, infra, credentials), Claude should say so and ask rather than guess.
