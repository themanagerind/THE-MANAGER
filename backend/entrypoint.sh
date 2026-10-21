#!/bin/sh
set -e

# Apply database migrations on startup unless AUTO_MIGRATE is set to false
if [ "$AUTO_MIGRATE" != "false" ]; then
    echo "[Railway Startup] Checking and applying database migrations..."
    alembic upgrade head
    echo "[Railway Startup] Migrations applied successfully."
fi

# Automatically seed Platform Owner if SEED_PLATFORM_OWNER_MOBILE is defined
if [ -n "$SEED_PLATFORM_OWNER_MOBILE" ]; then
    echo "[Railway Startup] Seeding Platform Owner account for mobile: $SEED_PLATFORM_OWNER_MOBILE..."
    python -m scripts.seed_platform_owner --mobile "$SEED_PLATFORM_OWNER_MOBILE" --name "${SEED_PLATFORM_OWNER_NAME:-Platform Owner}" || true
fi

echo "[Railway Startup] Starting FastAPI Uvicorn server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WORKERS:-4}"
