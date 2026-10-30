"""
Seed 20 Surat (Gujarat) societies, each with one ACTIVE Admin.

Login here is Mobile + OTP only (no passwords exist — see User model), so
an Admin's "credential" is their mobile number: they enter it on /login and
the OTP is sent by SMS (Twilio in production; echoed as dev_otp when
ENVIRONMENT=development).

The default admin mobiles below are PLACEHOLDERS (9000000101..9000000120)
so the script is runnable anywhere, but a placeholder can't receive an SMS.
For real logins pass the real numbers, one per society in the order of
SURAT_SOCIETIES:

    python -m scripts.seed_surat_societies
    python -m scripts.seed_surat_societies --mobiles 98xxxxxx01,98xxxxxx02,...

Safe to re-run: a society (same name + city) or an admin mobile that
already exists is skipped, not duplicated.
"""
import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.models.enums import Role, UserStatus
from app.models.identity import Society, User, UserRole
from app.schemas.society import SocietyCreateIn
from app.services import society_service

CITY = "Surat"
STATE = "Gujarat"

# (society name, area, pincode, admin name)
SURAT_SOCIETIES: list[tuple[str, str, str, str]] = [
    ("Shreeji Residency", "Adajan", "395009", "Rajesh Patel"),
    ("Sunrise Heights", "Vesu", "395007", "Kiran Desai"),
    ("Anand Park Society", "Piplod", "395007", "Hiren Shah"),
    ("Riverside Apartments", "Althan", "395017", "Mehul Mehta"),
    ("Green Valley Homes", "Pal", "395009", "Nilesh Joshi"),
    ("Silver Oak Residency", "City Light", "395007", "Jignesh Modi"),
    ("Krishna Kunj Society", "Athwa", "395001", "Bhavesh Thakkar"),
    ("Laxmi Nagar Apartments", "Varachha", "395006", "Dipak Gajera"),
    ("Shanti Niketan", "Katargam", "395004", "Ketan Vaghasiya"),
    ("Om Shanti Heights", "Udhna", "394210", "Paresh Rana"),
    ("Tapi View Residency", "Rander", "395005", "Sanjay Chauhan"),
    ("Royal Orchid Society", "Dumas Road", "395007", "Ashish Parekh"),
    ("Swastik Enclave", "Bhatar", "395017", "Vimal Bhatt"),
    ("Gokul Dham Society", "Ghod Dod Road", "395001", "Tushar Kapadia"),
    ("Pearl Residency", "Parle Point", "395007", "Chirag Sheth"),
    ("Sea Breeze Apartments", "Magdalla", "395007", "Yogesh Trivedi"),
    ("Navjivan Society", "Jahangirpura", "395005", "Mahesh Solanki"),
    ("Dev Darshan Residency", "Sarthana", "395006", "Rohit Dave"),
    ("Mangal Murti Apartments", "Nanpura", "395001", "Alpesh Naik"),
    ("Vrundavan Park", "Kapodra", "395006", "Dharmesh Italiya"),
]

DEFAULT_MOBILES = [str(9000000101 + i) for i in range(len(SURAT_SOCIETIES))]


async def seed(db: AsyncSession, mobiles: list[str]) -> list[dict]:
    """Create any missing society + Admin pairs. Returns one row per society
    (name, code, admin name, mobile, created) for the caller to print."""
    if len(mobiles) != len(SURAT_SOCIETIES):
        raise ValueError(f"Need exactly {len(SURAT_SOCIETIES)} mobiles, got {len(mobiles)}")
    if len(set(mobiles)) != len(mobiles):
        raise ValueError("Admin mobiles must be unique")

    results = []
    for (name, area, pincode, admin_name), mobile in zip(SURAT_SOCIETIES, mobiles):
        full_name = f"{name}, {area}"
        society = (
            await db.execute(select(Society).where(Society.name == full_name, Society.city == CITY))
        ).scalar_one_or_none()
        created = society is None
        if created:
            society = await society_service.create_society(
                db,
                SocietyCreateIn(
                    name=full_name,
                    address=f"{area}, {CITY}",
                    city=CITY,
                    state=STATE,
                    pincode=pincode,
                ),
            )

        admin = (
            await db.execute(
                select(User).where(User.society_id == society.id, User.mobile == mobile)
            )
        ).scalar_one_or_none()
        if admin is None:
            now = datetime.now(timezone.utc)
            admin = User(
                society_id=society.id,
                full_name=admin_name,
                mobile=mobile,
                status=UserStatus.ACTIVE,  # seeded by an operator — no approval step
                approved_at=now,
            )
            db.add(admin)
            await db.flush()
            db.add(
                UserRole(user_id=admin.id, role=Role.ADMIN, assigned_by=None, assigned_at=now)
            )
            await db.commit()
            created = True

        results.append(
            {
                "society": full_name,
                "code": society.code,
                "admin": admin_name,
                "mobile": mobile,
                "created": created,
            }
        )
    return results


async def _run(mobiles: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        rows = await seed(db, mobiles)
    print(f"{'Society':<42} {'Code':<16} {'Admin':<20} Mobile")
    for r in rows:
        mark = "" if r["created"] else "  (already existed)"
        print(f"{r['society']:<42} {r['code']:<16} {r['admin']:<20} {r['mobile']}{mark}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "--mobiles",
        help="Comma-separated 10-digit admin mobiles, one per society in order (default: placeholders)",
    )
    args = parser.parse_args()
    mobiles = [m.strip() for m in args.mobiles.split(",")] if args.mobiles else DEFAULT_MOBILES
    asyncio.run(_run(mobiles))


if __name__ == "__main__":
    main()
