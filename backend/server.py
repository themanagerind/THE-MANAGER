"""Supervisor entrypoint shim.

The Emergent environment's supervisor runs `uvicorn server:app` from /app/backend.
This project's real FastAPI app lives in app.main, so we re-export it here.

The Emergent supervisor is read-only and does NOT start PostgreSQL/Redis (this
repo's stack), and pod restarts wipe anything outside /app and /root. So before
importing the app we ensure that infrastructure is up (idempotent, fast no-op
when already running). Postgres data persists in /app/.pgdata.
"""
import os
import socket
import subprocess


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _ensure_infra() -> None:
    # Fast path: on normal hot-reloads both services are already up.
    if _port_open("localhost", 5432) and _port_open("localhost", 6379):
        return
    script = os.path.join(os.path.dirname(__file__), "bootstrap_env.sh")
    subprocess.run(["/bin/bash", script], check=False)


_ensure_infra()

from app.main import app  # noqa: E402

__all__ = ["app"]
