"""
Notify every active resident (Owner and/or Tenant, Section 12) on a
property whose maintenance due has gone overdue, once per due — powers
the Resident bell icon (Phase 1 in-app notifications, user-requested).

This is a periodic **ops task** (cron), not an API endpoint or in-app
scheduler — same reasoning as scripts/cleanup_orphan_proofs.py: there's
no background-job runner in this app to hang a periodic task off of.
Schedule it to run once daily, e.g.:

    0 8 * * * cd /path/to/backend && venv/bin/python -m scripts.generate_overdue_notifications

Usage:
    python -m scripts.generate_overdue_notifications
"""
import asyncio

from app.core.db import AsyncSessionLocal
from app.services import notification_service


async def _run() -> None:
    async with AsyncSessionLocal() as db:
        created = await notification_service.generate_overdue_notifications(db)
        print(f"{created} new overdue-maintenance notification(s) created")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
