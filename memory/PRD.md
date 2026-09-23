# PRD — Housing Society Management Platform

## Original request
User connected a GitHub repo and asked to run the project.

## What the project is
Multi-role housing society management platform (from GitHub).
- **Backend:** FastAPI + SQLAlchemy async + PostgreSQL + Redis + Alembic, JWT/OTP auth.
- **Frontend:** React 18 + TypeScript + Vite + Tailwind, PWA (offline queue).
- **Roles:** Platform Owner, Admin, Sub-admin, Manager, Guard, Resident.
- Modules: auth, residents, properties, payments, expense bills, complaints,
  visitors, amenities, notices, proposals, manager todos, staff, sub-admins, accounts.

## Environment adaptation (done 2026-09-23)
The repo's native stack differs from the Emergent default (Mongo/CRA). Adapted to run:
- Installed & started **PostgreSQL** (db/user `housing`) and **Redis** (localhost:6379).
- Created `/app/backend/server.py` re-exporting `app.main:app` (supervisor runs `uvicorn server:app` on :8001).
- Created `/app/backend/.env` (DATABASE_URL asyncpg, REDIS_URL, JWT_SECRET_KEY).
- Ran `alembic upgrade head` (all tables created).
- Seeded Platform Owner (mobile 9999999999).
- Frontend: added `start` script + Vite `host/port 3000/allowedHosts`; proxy target → :8001; `yarn install --ignore-engines`.

## Status
- Backend running on :8001 — `/health` OK, `/docs` 200, OTP→verify→JWT login verified e2e.
- Frontend running on :3000 — login page ("Society Manager") renders.

## ⚠️ Caveat
PostgreSQL & Redis were started manually (not under the read-only supervisor).
After a pod restart, restart them:
```bash
pg_ctlcluster 15 main start ; redis-server --daemonize yes --port 6379
```

## Backlog / next
- P1: Finish Admin/Sub-admin/Guard placeholder pages (wire to existing backend APIs).
- P2: Real SMS provider for OTP (currently mocked), object storage for payment proofs.
