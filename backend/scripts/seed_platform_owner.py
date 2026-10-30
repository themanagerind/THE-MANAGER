"""
Bootstrap the first Platform Owner account.

Section 5 defines what a Platform Owner does, but not who creates the very
first one — by definition, nobody above them exists to approve it. This is
therefore a one-time **ops task**, not an API endpoint (an unauthenticated
"create a Platform Owner" endpoint would be a serious, unspecified security
hole — Master Rule: don't invent an unspecified workflow).

Usage:
    python -m scripts.seed_platform_owner --mobile 9999999999 --name "Ops Admin"
"""
import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.enums import Role, UserStatus
from app.models.identity import User, UserRole


async def _seed(mobile: str, name: str) -> None:
    async with AsyncSessionLocal() as db:
        existing = (
            await db.execute(select(User).where(User.mobile == mobile, User.society_id.is_(None)))
        ).scalar_one_or_none()
        if existing is not None:
            print(f"Platform Owner already exists for mobile {mobile} (user_id={existing.id})")
            return

        owner = User(
            society_id=None,
            full_name=name,
            mobile=mobile,
            status=UserStatus.ACTIVE,  # no approval step above Platform Owner
        )
        db.add(owner)
        await db.flush()
        db.add(
            UserRole(
                user_id=owner.id,
                role=Role.PLATFORM_OWNER,
                assigned_by=None,
                assigned_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
        print(f"Platform Owner created: user_id={owner.id}, mobile={mobile}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mobile", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    asyncio.run(_seed(args.mobile, args.name))


if __name__ == "__main__":
    main()
