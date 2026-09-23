"""
Society service — Section 5 (Platform Owner), Section 6 (Admin), Section 25
(society status), Section 26 (Admin approval flow).
"""
import secrets
import string
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.models.enums import HouseType, LocationType, Role, SocietyStatus, UserStatus
from app.models.identity import Property, Society, SocietyLocation, User, UserRole
from app.schemas.property import (
    BungalowStructureIn,
    FlatsStructureIn,
    SocietyLocationCreateIn,
    SocietyLocationUpdateIn,
)
from app.schemas.society import SocietyCreateIn, SocietySignupIn, SocietyUpdateIn
from app.services import property_service

_CODE_SUFFIX_LENGTH = 5
_CODE_GENERATION_MAX_ATTEMPTS = 10


def _code_prefix_from_name(name: str) -> str:
    slug = "".join(ch for ch in name.upper() if ch.isalnum())[:8]
    return slug or "SOC"


async def _generate_unique_code(db: AsyncSession, name: str) -> str:
    """Never client-supplied (see SocietyCreateIn's docstring) — two
    societies can never collide on code, and a Platform Owner never has
    to think one up. A short random suffix (not a sequential counter)
    keeps codes from being guessable in order. The DB's own UNIQUE
    constraint on Society.code is the final backstop if this ever raced
    with itself, but Platform Owner society-creation isn't a
    high-concurrency path, so a plain check-then-generate loop is enough."""
    prefix = _code_prefix_from_name(name)
    for _ in range(_CODE_GENERATION_MAX_ATTEMPTS):
        suffix = "".join(secrets.choice(string.digits) for _ in range(_CODE_SUFFIX_LENGTH))
        code = f"{prefix}-{suffix}"
        existing = (await db.execute(select(Society).where(Society.code == code))).scalar_one_or_none()
        if existing is None:
            return code
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Could not generate a unique society code — try again")

_SEARCH_MIN_QUERY_LENGTH = 3
_SEARCH_RESULT_LIMIT = 10
_SEARCH_MAX_PER_WINDOW = 30
_SEARCH_RATE_WINDOW_SECONDS = 600


def _search_rate_key(client_ip: str) -> str:
    return f"society_search:rate:{client_ip}"


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def create_society(db: AsyncSession, body: SocietyCreateIn) -> Society:
    """Platform Owner creates a society directly — this is the only path
    for a society to exist now that Admin signup targets an existing one
    instead of bundling a new society with it. Goes straight to ACTIVE:
    the Platform Owner creating it from their own dashboard IS the
    approval, there's no one else who needs to sign off on it. `locations`
    is the only optional field on the request — if given, each Wing/Row
    is created in the same transaction as the society itself (single
    commit at the end), so a Platform Owner doesn't have to hand off to
    the Admin just to get the first Wing/Row on record."""
    code = await _generate_unique_code(db, body.name)
    society = Society(
        name=body.name, code=code, status=SocietyStatus.ACTIVE,
        address=body.address, city=body.city, state=body.state, pincode=body.pincode,
    )
    db.add(society)
    await db.flush()  # need society.id before adding locations below

    for loc in body.locations:
        db.add(SocietyLocation(society_id=society.id, name=loc.name, location_type=loc.location_type))

    await db.commit()
    await db.refresh(society)
    return society


async def _get_society_or_404(db: AsyncSession, society_id: uuid.UUID) -> Society:
    society = (await db.execute(select(Society).where(Society.id == society_id))).scalar_one_or_none()
    if society is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Society not found")
    return society


async def update_society_profile(db: AsyncSession, society_id: uuid.UUID, body: SocietyUpdateIn) -> Society:
    """Platform Owner edits a society's profile after creation — name and
    address details only; `code` stays fixed (see SocietyUpdateIn's
    docstring). Locations are edited separately, via
    list_society_locations/add_society_location below."""
    society = await _get_society_or_404(db, society_id)

    society.name = body.name
    society.address = body.address
    society.city = body.city
    society.state = body.state
    society.pincode = body.pincode
    await db.commit()
    await db.refresh(society)
    return society


async def list_society_locations(db: AsyncSession, society_id: uuid.UUID) -> list[SocietyLocation]:
    """Platform Owner viewing a society's Wings/Rows from the Societies
    page's Edit modal — the same rows the Admin sees on their own
    Properties page (property_service.list_locations is society-scoped,
    not current-user-scoped, so it's reused as-is here)."""
    await _get_society_or_404(db, society_id)
    return await property_service.list_locations(db, society_id)


async def add_society_location(
    db: AsyncSession, society_id: uuid.UUID, body: SocietyLocationCreateIn
) -> SocietyLocation:
    """Platform Owner adding a Wing/Row to an existing society from the
    Edit modal — the Admin can still do this from their own Properties
    page too; both paths write the same table."""
    await _get_society_or_404(db, society_id)
    return await property_service.create_location(db, society_id, body)


async def update_society_location(
    db: AsyncSession, society_id: uuid.UUID, location_id: uuid.UUID, body: SocietyLocationUpdateIn
) -> SocietyLocation:
    """Platform Owner renaming (or, if unused, retyping) an existing
    Wing/Row from the Edit modal."""
    await _get_society_or_404(db, society_id)
    return await property_service.update_location(db, society_id, location_id, body)


_STRUCTURE_CONFLICT_MESSAGE = (
    "Generating this structure collided with an existing Tower/Row name or "
    "house number in this society — check what's already on record first."
)


async def generate_flats_structure(
    db: AsyncSession, society_id: uuid.UUID, body: FlatsStructureIn
) -> list[Property]:
    """Bulk-generates `tower_count` Wings, each with `floors_per_tower`
    floors of `flats_per_floor` FLAT properties — every tower/floor/flat
    combination in one atomic transaction (single final commit, only
    flush() for the intermediate Wing ids, same pattern as
    create_society's locations loop above)."""
    await _get_society_or_404(db, society_id)

    towers = [
        SocietyLocation(society_id=society_id, name=f"Tower {t}", location_type=LocationType.WING)
        for t in range(1, body.tower_count + 1)
    ]
    db.add_all(towers)
    await db.flush()  # need tower.id before adding flats below

    properties: list[Property] = []
    for t_idx, tower in enumerate(towers, start=1):
        for floor in range(1, body.floors_per_tower + 1):
            for unit in range(1, body.flats_per_floor + 1):
                properties.append(
                    Property(
                        society_id=society_id,
                        location_id=tower.id,
                        house_number=f"T{t_idx}-{floor}{unit:02d}",
                        house_type=HouseType.FLAT,
                        floor_number=floor,
                        status="ACTIVE",
                    )
                )
    db.add_all(properties)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, _STRUCTURE_CONFLICT_MESSAGE)
    for p in properties:
        await db.refresh(p)
    return properties


async def generate_bungalow_structure(
    db: AsyncSession, society_id: uuid.UUID, body: BungalowStructureIn
) -> list[Property]:
    """Bulk-generates `row_count` Rows, each with `houses_per_row` BUNGALOW
    properties — every house starts at floors_above_ground=0 (ground floor
    only, which is always implied); additional storeys are set per-house
    afterward via update_property_floors_above_ground, since that varies
    house to house and can't be captured by a single bulk count."""
    await _get_society_or_404(db, society_id)

    rows = [
        SocietyLocation(society_id=society_id, name=f"Row {r}", location_type=LocationType.ROW)
        for r in range(1, body.row_count + 1)
    ]
    db.add_all(rows)
    await db.flush()  # need row.id before adding houses below

    properties: list[Property] = []
    for r_idx, row in enumerate(rows, start=1):
        for h in range(1, body.houses_per_row + 1):
            properties.append(
                Property(
                    society_id=society_id,
                    location_id=row.id,
                    house_number=f"R{r_idx}-{h}",
                    house_type=HouseType.BUNGALOW,
                    floor_number=None,
                    floors_above_ground=0,
                    status="ACTIVE",
                )
            )
    db.add_all(properties)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, _STRUCTURE_CONFLICT_MESSAGE)
    for p in properties:
        await db.refresh(p)
    return properties


async def update_property_floors_above_ground(
    db: AsyncSession, society_id: uuid.UUID, property_id: uuid.UUID, floors_above_ground: int
) -> Property:
    """Sets how many storeys are built above one BUNGALOW house's
    (always-implied) ground floor — the per-house follow-up step after
    generate_bungalow_structure()."""
    prop = (
        await db.execute(
            select(Property).where(Property.id == property_id, Property.society_id == society_id)
        )
    ).scalar_one_or_none()
    if prop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Property not found in this society")
    if prop.house_type != HouseType.BUNGALOW:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "floors_above_ground only applies to BUNGALOW houses"
        )

    prop.floors_above_ground = floors_above_ground
    await db.commit()
    await db.refresh(prop)
    return prop


async def lookup_society_by_code(db: AsyncSession, code: str) -> Society | None:
    """Public lookup for the Admin/Resident signup forms — only returns an
    ACTIVE society (a PENDING or SUSPENDED one isn't accepting anyone
    signing up against it)."""
    return (
        await db.execute(
            select(Society).where(Society.code == code, Society.status == SocietyStatus.ACTIVE)
        )
    ).scalar_one_or_none()


async def search_societies_by_name(db: AsyncSession, query: str, client_ip: str) -> list[Society]:
    """Public name-search alternative to the exact-code lookup above, for a
    signup picker instead of asking Admin/Resident to already know the
    code. Kept narrow so it can't become the full-directory-enumeration
    endpoint SocietyLookupOut's docstring deliberately avoids: a minimum
    query length, a capped result count, and a per-IP rate limit (there's
    no mobile number yet at this point in signup to key on, unlike the
    OTP/signup rate limits elsewhere)."""
    trimmed = query.strip()
    if len(trimmed) < _SEARCH_MIN_QUERY_LENGTH:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Search needs at least {_SEARCH_MIN_QUERY_LENGTH} characters",
        )

    r = get_redis()
    attempts = await r.incr(_search_rate_key(client_ip))
    if attempts == 1:
        await r.expire(_search_rate_key(client_ip), _SEARCH_RATE_WINDOW_SECONDS)
    if attempts > _SEARCH_MAX_PER_WINDOW:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many searches — try again later")

    pattern = f"%{_escape_like(trimmed)}%"
    return (
        await db.execute(
            select(Society)
            .where(Society.status == SocietyStatus.ACTIVE, Society.name.ilike(pattern, escape="\\"))
            .order_by(Society.name)
            .limit(_SEARCH_RESULT_LIMIT)
        )
    ).scalars().all()


async def signup_society_and_admin(db: AsyncSession, body: SocietySignupIn) -> tuple[Society, User]:
    existing = (
        await db.execute(select(Society).where(Society.code == body.society_code))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Society code already in use")

    society = Society(
        name=body.society_name,
        code=body.society_code,
        status=SocietyStatus.PENDING,
        address=body.address,
        city=body.city,
        state=body.state,
        pincode=body.pincode,
    )
    db.add(society)
    await db.flush()  # get society.id without committing yet

    admin = User(
        society_id=society.id,
        full_name=body.admin_full_name,
        mobile=body.admin_mobile,
        email=body.admin_email,
        status=UserStatus.PENDING,
    )
    db.add(admin)
    await db.flush()

    # Role row created now, but login is gated on User.status == ACTIVE
    # regardless (get_current_user / resolve_login) — see Auth module.
    db.add(
        UserRole(
            user_id=admin.id,
            role=Role.ADMIN,
            assigned_by=None,  # self-signup, not assigned by another user
            assigned_at=datetime.now(timezone.utc),
        )
    )

    await db.commit()
    await db.refresh(society)
    await db.refresh(admin)
    return society, admin


async def list_societies(db: AsyncSession) -> list[Society]:
    return (await db.execute(select(Society))).scalars().all()


async def approve_society_and_admin(
    db: AsyncSession, society_id: uuid.UUID, approved_by: uuid.UUID
) -> Society:
    """Platform Owner approves a pending society — activates the society AND
    its founding Admin(s) together (Section 26: Admin approval flow)."""
    society = (await db.execute(select(Society).where(Society.id == society_id))).scalar_one_or_none()
    if society is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Society not found")
    if society.status != SocietyStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Society is already {society.status.value}")

    society.status = SocietyStatus.ACTIVE

    admins = (
        await db.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .where(
                User.society_id == society_id,
                UserRole.role == Role.ADMIN,
                UserRole.revoked_at.is_(None),
                User.status == UserStatus.PENDING,
            )
        )
    ).scalars().all()
    now = datetime.now(timezone.utc)
    for admin in admins:
        admin.status = UserStatus.ACTIVE
        admin.approved_by = approved_by
        admin.approved_at = now

    await db.commit()
    await db.refresh(society)
    return society


async def update_society_status(
    db: AsyncSession, society_id: uuid.UUID, new_status: SocietyStatus
) -> Society:
    """Section 25: PENDING -> ACTIVE -> SUSPENDED, Platform Owner controls it.
    (Use /approve for the initial PENDING->ACTIVE + admin-activation step;
    this endpoint is for subsequent SUSPENDED<->ACTIVE transitions.)

    Audit fix: the docstring's contract wasn't enforced — new_status was
    assigned unconditionally, so a Platform Owner could send PENDING at any
    time (ACTIVE -> PENDING, SUSPENDED -> PENDING), or "approve" an already
    non-PENDING society through this endpoint. PENDING is only ever reached
    via signup, and only ever left via /approve."""
    society = (await db.execute(select(Society).where(Society.id == society_id))).scalar_one_or_none()
    if society is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Society not found")

    if new_status == SocietyStatus.PENDING:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cannot set status to PENDING — that's the initial signup state, not a transition target",
        )
    if society.status == SocietyStatus.PENDING:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Society is still PENDING — use POST /societies/{id}/approve first",
        )

    society.status = new_status
    await db.commit()
    await db.refresh(society)
    return society
