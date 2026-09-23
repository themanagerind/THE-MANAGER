"""Supervisor entrypoint shim.

The Emergent environment's supervisor runs `uvicorn server:app` from /app/backend.
This project's real FastAPI app lives in app.main, so we re-export it here.
"""
from app.main import app

__all__ = ["app"]
