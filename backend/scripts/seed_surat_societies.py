"""
Seed 20 Surat (Gujarat) societies, each with one ACTIVE Admin, one Wing with
four flats, and a few Residents (owners/tenants) living in those flats.

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
    python -m scripts.seed_surat_societies --residents-per-society 0   # admins only

Resident mobiles are also placeholders: 9000100000 + society_index*10 + n.

Safe to re-run: a society (same name + city), an existing active Admin, a
flat or a resident mobile that already exists is skipped, not duplicated.
"""
import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.models.enums import HouseType, LocationType, RelationshipType, Role, UserStatus
from app.models.identity import (
    Property,
    PropertyResident,
    Society,
    SocietyLocation,
    User,
    UserRole,
)
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

WING = "A"
FLATS = [("A-101", 1), ("A-102", 1), ("A-201", 2), ("A-202", 2)]  # (house number, floor)
MAX_RESIDENTS_PER_SOCIETY = len(FLATS)

_FIRST = ["Amit", "Neha", "Priya", "Vikas", "Pooja", "Harsh", "Komal", "Jay", "Riddhi", "Smit"]
_LAST = ["Patel", "Shah", "Desai", "Mehta", "Joshi", "Modi", "Parmar", "Rana", "Trivedi", "Gandhi"]


def resident_mobile(society_index: int, n: int) -> str:
    return str(9000100000 + society_index * 10 + n)


def resident_name(society_index: int, n: int) -> str:
    k = society_index * MAX_RESIDENTS_PER_SOCIETY + n
    return f"{_FIRST[k % len(_FIRST)]} {_LAST[(k // len(_FIRST) + k) % len(_LAST)]}"


async def _seed_residents(
    db: AsyncSession, society: Society, society_index: int, count: int
) -> list[dict]:
    """One Wing, four flats, and `count` Residents (first two OWNER, the rest
    TENANT) each living in their own flat. Returns [{name, mobile, flat}]."""
    if count <= 0:
        return []
    count = min(count, MAX_RESIDENTS_PER_SOCIETY)
    wing = (
        await db.execute(
            select(SocietyLocation).where(
                SocietyLocation.society_id == society.id,
                SocietyLocation.location_type == LocationType.WING,
                SocietyLocation.name == WING,
            )
        )
    ).scalar_one_or_none()
    if wing is None:
        wing = SocietyLocation(society_id=society.id, name=WING, location_type=LocationType.WING)
        db.add(wing)
        await db.flush()

    out = []
    now = datetime.now(timezone.utc)
    for n, (house_number, floor) in enumerate(FLATS[:count]):
        flat = (
            await db.execute(
                select(Property).where(
                    Property.society_id == society.id, Property.house_number == house_number
                )
            )
        ).scalar_one_or_none()
        if flat is None:
            flat = Property(
                society_id=society.id,
                location_id=wing.id,
                house_number=house_number,
                house_type=HouseType.FLAT,
                floor_number=floor,
            )
            db.add(flat)
            await db.flush()

        mobile = resident_mobile(society_index, n)
        resident = (
            await db.execute(
                select(User).where(User.society_id == society.id, User.mobile == mobile)
            )
        ).scalar_one_or_none()
        if resident is None:
            resident = User(
                society_id=society.id,
                full_name=resident_name(society_index, n),
                mobile=mobile,
                status=UserStatus.ACTIVE,
                approved_at=now,
            )
            db.add(resident)
            await db.flush()
            db.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_by=None, assigned_at=now))
            db.add(
                PropertyResident(
                    society_id=society.id,
                    property_id=flat.id,
                    resident_id=resident.id,
                    relationship_type=RelationshipType.OWNER if n < 2 else RelationshipType.TENANT,
                    is_active=True,
                    start_date=now.date(),
                    created_at=now,
                )
            )
        out.append({"name": resident.full_name, "mobile": resident.mobile, "flat": house_number})
    await db.commit()
    return out


async def seed(
    db: AsyncSession, mobiles: list[str], residents_per_society: int = 3
) -> list[dict]:
    """Create any missing society + Admin (+ flats and Residents) sets. Returns
    one row per society (name, code, admin name, mobile, residents, created)
    for the caller to print."""
    if len(mobiles) != len(SURAT_SOCIETIES):
        raise ValueError(f"Need exactly {len(SURAT_SOCIETIES)} mobiles, got {len(mobiles)}")
    if len(set(mobiles)) != len(mobiles):
        raise ValueError("Admin mobiles must be unique")

    results = []
    for index, ((name, area, pincode, admin_name), mobile) in enumerate(
        zip(SURAT_SOCIETIES, mobiles)
    ):
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

        # One active Admin per society (DB rule) — if the society already has
        # one, keep it as-is and report its mobile instead of adding another.
        admin = (
            await db.execute(
                select(User)
                .join(UserRole, UserRole.user_id == User.id)
                .where(
                    User.society_id == society.id,
                    UserRole.role == Role.ADMIN,
                    UserRole.revoked_at.is_(None),
                )
            )
        ).scalars().first()
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

        residents = await _seed_residents(db, society, index, residents_per_society)

        results.append(
            {
                "society": full_name,
                "code": society.code,
                "admin": admin.full_name,
                "mobile": admin.mobile,
                "residents": residents,
                "created": created,
            }
        )
    return results


async def _run(mobiles: list[str], residents_per_society: int) -> None:
    async with AsyncSessionLocal() as db:
        rows = await seed(db, mobiles, residents_per_society)
    print(f"{'Society':<42} {'Code':<16} {'Admin':<20} Mobile")
    for r in rows:
        mark = "" if r["created"] else "  (already existed)"
        print(f"{r['society']:<42} {r['code']:<16} {r['admin']:<20} {r['mobile']}{mark}")
        for res in r["residents"]:
            print(f"    resident {res['flat']:<6} {res['name']:<20} {res['mobile']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "--mobiles",
        help="Comma-separated 10-digit admin mobiles, one per society in order (default: placeholders)",
    )
    parser.add_argument(
        "--residents-per-society",
        type=int,
        default=3,
        help=f"Residents to add per society, 0-{MAX_RESIDENTS_PER_SOCIETY} (default 3: 2 owners + 1 tenant)",
    )
    args = parser.parse_args()
    mobiles = [m.strip() for m in args.mobiles.split(",")] if args.mobiles else DEFAULT_MOBILES
    asyncio.run(_run(mobiles, args.residents_per_society))


if __name__ == "__main__":
    main()
