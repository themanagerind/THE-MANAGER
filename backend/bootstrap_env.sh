#!/bin/bash
# Idempotent infrastructure bring-up for this repo's non-default stack
# (PostgreSQL + Redis). The Emergent supervisor is read-only and only
# autostarts the backend/frontend/mongodb — it does NOT start Postgres or
# Redis, and container/pod restarts wipe anything outside /app and /root.
# server.py calls this on backend start so auth (which needs Redis) and the
# DB come up automatically. Postgres data lives in /app/.pgdata so it
# survives pod restarts.
PGDATA=/app/.pgdata
PGBIN=/usr/lib/postgresql/15/bin
BACKEND_DIR=/app/backend

echo "[bootstrap] starting infra bring-up"

# --- Redis (ephemeral cache/OTP store — safe to lose on restart) ---
if ! redis-cli -p 6379 ping >/dev/null 2>&1; then
  redis-server --daemonize yes --port 6379 >/tmp/redis-boot.log 2>&1
  echo "[bootstrap] redis started"
fi

# --- Stop the default apt cluster if it grabbed :5432 (we use /app/.pgdata) ---
if [ -d /var/lib/postgresql/15/main ]; then
  su postgres -c "$PGBIN/pg_ctl -D /var/lib/postgresql/15/main stop -m fast" >/dev/null 2>&1 || true
fi

# --- Postgres: init persistent data dir on first ever run ---
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  echo "[bootstrap] initializing persistent postgres data dir at $PGDATA"
  mkdir -p "$PGDATA"
  chown -R postgres:postgres "$PGDATA"
  su postgres -c "$PGBIN/initdb -D $PGDATA" >/tmp/pg-initdb.log 2>&1
fi
chown -R postgres:postgres "$PGDATA" 2>/dev/null || true

# --- Start postgres if not already accepting connections ---
if ! su postgres -c "$PGBIN/pg_isready -p 5432" >/dev/null 2>&1; then
  su postgres -c "$PGBIN/pg_ctl -D $PGDATA -l $PGDATA/server.log -o '-p 5432' -w -t 30 start" >/tmp/pg-start.log 2>&1
  echo "[bootstrap] postgres started"
fi

# --- Ensure role + database exist (idempotent) ---
su postgres -c "psql -p 5432 -tc \"SELECT 1 FROM pg_roles WHERE rolname='housing'\"" 2>/dev/null | grep -q 1 || \
  su postgres -c "psql -p 5432 -c \"CREATE USER housing WITH PASSWORD 'housing' SUPERUSER;\"" >/dev/null 2>&1
su postgres -c "psql -p 5432 -tc \"SELECT 1 FROM pg_database WHERE datname='housing'\"" 2>/dev/null | grep -q 1 || \
  su postgres -c "psql -p 5432 -c \"CREATE DATABASE housing OWNER housing;\"" >/dev/null 2>&1

# --- Apply migrations + seed the bootstrap Platform Owner (both idempotent) ---
cd "$BACKEND_DIR" || exit 0
/root/.venv/bin/alembic upgrade head >/tmp/alembic-boot.log 2>&1 && echo "[bootstrap] migrations applied"
/root/.venv/bin/python -m scripts.seed_platform_owner --mobile 9999999999 --name "Platform Owner" >/tmp/seed-boot.log 2>&1 || true

echo "[bootstrap] infra bring-up complete"
