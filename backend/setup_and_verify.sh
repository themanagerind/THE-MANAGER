#!/usr/bin/env bash
# One-command environment setup + verification, so "asyncpg missing" (or
# any other dependency-not-installed) never blocks a review again.
#
# Prerequisites this script does NOT install for you (needs your machine's
# package manager / Docker): a running PostgreSQL server and a running
# Redis server, reachable at the URLs below (override via env vars).
#
# Usage:
#   TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/housing_test \
#   TEST_REDIS_URL=redis://localhost:6379/15 \
#   ./setup_and_verify.sh

set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/5: Installing dependencies =="
pip install -r requirements.txt -r requirements-dev.txt

export TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql+asyncpg://postgres:postgres@localhost:5432/housing_test}"
export TEST_REDIS_URL="${TEST_REDIS_URL:-redis://localhost:6379/15}"
export DATABASE_URL="${DATABASE_URL:-$TEST_DATABASE_URL}"
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-local-dev-secret-change-me}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

echo "== 2/5: Verifying the app imports and every route wires correctly =="
python3 -c "
from app.main import app
n = sum(len(m) for m in app.openapi()['paths'].values())
print(f'App import OK — {n} routes registered')
"

echo "== 3/5: Running Alembic migrations against the REAL test database =="
alembic upgrade head
echo "Migrations applied. Current revision:"
alembic current

echo "== 4/5: Verifying the role/society DB trigger actually rejects a bad insert =="
python3 -c "
import asyncio, uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.identity import User, UserRole
from app.models.enums import Role, UserStatus

async def main():
    engine = create_async_engine('$TEST_DATABASE_URL')
    Session = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with Session() as db:
        # A society-bound user (society_id NOT NULL) given PLATFORM_OWNER
        # must be REJECTED by the DB trigger (0002_role_society_trigger.py).
        from app.models.identity import Society
        from app.models.enums import SocietyStatus
        soc = Society(name='Trigger Test Soc', code=f'TRG-{uuid.uuid4().hex[:8]}', status=SocietyStatus.ACTIVE)
        db.add(soc); await db.flush()
        u = User(society_id=soc.id, full_name='Bad Owner', mobile=f'9{uuid.uuid4().hex[:9]}', status=UserStatus.ACTIVE)
        db.add(u); await db.flush()
        db.add(UserRole(user_id=u.id, role=Role.PLATFORM_OWNER, assigned_at=datetime.now(timezone.utc)))
        try:
            await db.commit()
            print('FAIL: trigger did not reject an invalid PLATFORM_OWNER assignment')
            raise SystemExit(1)
        except Exception as e:
            await db.rollback()
            print('OK: DB trigger rejected the invalid write as expected')
    await engine.dispose()

asyncio.run(main())
"

echo "== 5/5: Running the full pytest suite (real Postgres + Redis) =="
pytest tests/ -v

echo ""
echo "All checks passed. See docs/API_CONTRACT.md and docs/openapi_snapshot.json"
echo "for the frozen contract before starting frontend integration."
