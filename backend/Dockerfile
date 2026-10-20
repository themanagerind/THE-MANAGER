# Production image — CLAUDE.md Section 2 ("Docker deployment") and the
# repo layout in Section 4 both reference this file; it didn't exist yet.
# Runs the FastAPI app with uvicorn directly (no gunicorn in
# requirements.txt) using multiple worker processes — sufficient for a
# single-container deployment; put a process manager or multiple
# container replicas in front of this for horizontal scaling instead of
# adding gunicorn here.
FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg/asyncpg builds and healthchecks (curl used by
# the HEALTHCHECK below) — kept minimal and removed from the apt cache in
# the same layer to keep the image small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Installs from the full exact pin (requirements.lock.txt), not the
# human-edited requirements.txt (>= constraints, no transitive pins) —
# a production image build needs to be reproducible, not pick up
# whatever the latest compatible version happens to resolve to on build
# day. See requirements.lock.txt's own header for how to regenerate it.
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

# Runs as a non-root user — Section 3 (security hardening). uploads/ must
# be writable by this user (see UPLOAD_DIR in app/core/config.py, default
# "uploads" — mount this as a volume in production so files survive
# container restarts/redeploys instead of living in the writable layer).
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/uploads \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Migrations are NOT run here — run `alembic upgrade head` as a separate
# deploy step (once, before traffic is routed to new containers), never
# automatically on every container start: with multiple replicas that
# would race each other to apply the same migration concurrently.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
