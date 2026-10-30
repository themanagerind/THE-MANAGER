"""
Delete payment-proof files under settings.upload_dir that no PaymentProof
row references (audit finding: a Resident who uploads a proof and then
never submits the payment leaves that file on disk forever — nothing in
the request/submit flow itself can clean it up, since the file is written
before the Payment/PaymentProof rows exist).

Only ever deletes a file older than --min-age-hours (default 24) — a file
younger than that may belong to an in-flight upload -> submit sequence
that just hasn't reached submit_payment() yet.

This is a periodic **ops task** (cron), not an API endpoint or in-app
scheduler — same reasoning as scripts/seed_platform_owner.py: there's no
background-job runner in this app to hang a periodic task off of.

Usage:
    python -m scripts.cleanup_orphan_proofs                # apply
    python -m scripts.cleanup_orphan_proofs --dry-run       # report only
    python -m scripts.cleanup_orphan_proofs --min-age-hours 48
"""
import argparse
import asyncio
import time
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.models.payments import PaymentProof

settings = get_settings()


async def _referenced_storage_keys() -> set[str]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(PaymentProof.file_url))).scalars().all()
        return set(rows)


async def _cleanup(min_age_hours: float, dry_run: bool) -> None:
    proof_dir = Path(settings.upload_dir) / "payment_proofs"
    if not proof_dir.exists():
        print(f"{proof_dir} does not exist — nothing to do")
        return

    referenced = await _referenced_storage_keys()
    cutoff = time.time() - min_age_hours * 3600

    deleted = 0
    freed_bytes = 0
    for f in proof_dir.iterdir():
        if not f.is_file():
            continue
        storage_key = f"payment_proofs/{f.name}"
        if storage_key in referenced:
            continue
        if f.stat().st_mtime > cutoff:
            continue  # too recent — might still be mid-submission

        size = f.stat().st_size
        if dry_run:
            print(f"[dry-run] would delete {f} ({size} bytes)")
        else:
            f.unlink()
            print(f"deleted {f} ({size} bytes)")
        deleted += 1
        freed_bytes += size

    verb = "would free" if dry_run else "freed"
    print(f"\n{deleted} orphaned file(s), {verb} {freed_bytes / (1024 * 1024):.1f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-age-hours", type=float, default=24.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(_cleanup(args.min_age_hours, args.dry_run))


if __name__ == "__main__":
    main()
