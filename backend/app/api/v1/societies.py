"""Societies endpoints — public signup + Platform Owner administration."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.property import (
    BungalowStructureIn,
    FlatsStructureIn,
    PropertyCreateIn,
    PropertyFloorsUpdateIn,
    PropertyOut,
    SocietyLocationCreateIn,
    SocietyLocationOut,
    SocietyLocationUpdateIn,
)
from app.schemas.society import (
    SocietyCreateIn,
    SocietyLookupOut,
    SocietyOut,
    SocietySearchResultOut,
    SocietySignupIn,
    SocietySignupOut,
    SocietyStatusUpdateIn,
    SocietyUpdateIn,
)
from app.services import property_service, society_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/societies", tags=["societies"])


@router.get("/lookup/{code}", response_model=SocietyLookupOut)
async def lookup(code: str, db: Annotated[AsyncSession, Depends(get_db)]) -> SocietyLookupOut:
    """Public — used by the Admin/Resident signup forms to find their
    society by its code without needing its internal UUID, and without
    exposing the full society list."""
    society = await society_service.lookup_society_by_code(db, code)
    if society is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Society not found")
    return SocietyLookupOut(id=society.id, name=society.name)


@router.get("/search", response_model=list[SocietySearchResultOut])
async def search(
    q: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SocietySearchResultOut]:
    """Public — lets the Admin/Resident signup forms offer a name-search
    picker as an alternative to typing the exact code. Narrower than
    `lookup` above only in that it matches by substring instead of an
    exact code; see society_service.search_societies_by_name for the
    limits (min query length, capped results, per-IP rate limit) that
    keep this from becoming a full-directory-enumeration endpoint."""
    client_ip = request.client.host if request.client else "unknown"
    societies = await society_service.search_societies_by_name(db, q, client_ip)
    return [SocietySearchResultOut(id=s.id, name=s.name, city=s.city) for s in societies]


@router.post("/signup", response_model=SocietySignupOut)
async def signup(
    body: SocietySignupIn, db: Annotated[AsyncSession, Depends(get_db)]
) -> SocietySignupOut:
    """Public — no auth required. Creates a PENDING society + PENDING Admin
    together; both wait for Platform Owner approval (Section 26)."""
    society, admin = await society_service.signup_society_and_admin(db, body)
    return SocietySignupOut(society_id=society.id, admin_user_id=admin.id)


@router.get("", response_model=list[SocietyOut])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> list[SocietyOut]:
    societies = await society_service.list_societies(db)
    return [SocietyOut.model_validate(s) for s in societies]


@router.post("", response_model=SocietyOut)
async def create(
    body: SocietyCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> SocietyOut:
    """A society now only comes into existence this way — created directly
    by the Platform Owner from their dashboard, ACTIVE immediately. Admin
    signup (POST /admins/signup) targets an existing society created here;
    it no longer creates one itself."""
    society = await society_service.create_society(db, body)
    return SocietyOut.model_validate(society)


@router.post("/{society_id}/approve", response_model=SocietyOut)
async def approve(
    society_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> SocietyOut:
    society = await society_service.approve_society_and_admin(db, society_id, current.user_id)
    return SocietyOut.model_validate(society)


@router.patch("/{society_id}", response_model=SocietyOut)
async def update_profile(
    society_id: uuid.UUID,
    body: SocietyUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> SocietyOut:
    """Edits name/address/city/state/pincode — `code` and locations aren't
    editable here (see SocietyUpdateIn's docstring)."""
    society = await society_service.update_society_profile(db, society_id, body)
    return SocietyOut.model_validate(society)


@router.get("/{society_id}/locations", response_model=list[SocietyLocationOut])
async def list_locations(
    society_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> list[SocietyLocationOut]:
    """Platform Owner viewing a society's Wings/Rows from the Societies
    page's Edit modal, without switching into that society's Admin role."""
    locations = await society_service.list_society_locations(db, society_id)
    return [SocietyLocationOut.model_validate(loc) for loc in locations]


@router.post("/{society_id}/locations", response_model=SocietyLocationOut)
async def add_location(
    society_id: uuid.UUID,
    body: SocietyLocationCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> SocietyLocationOut:
    """Platform Owner adding a Wing/Row to an existing society — same
    table the Admin's own POST /properties/locations writes to."""
    location = await society_service.add_society_location(db, society_id, body)
    return SocietyLocationOut.model_validate(location)


@router.patch("/{society_id}/locations/{location_id}", response_model=SocietyLocationOut)
async def update_location(
    society_id: uuid.UUID,
    location_id: uuid.UUID,
    body: SocietyLocationUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> SocietyLocationOut:
    """Platform Owner renaming (or, if unused, retyping) an existing
    Wing/Row from the Edit modal."""
    location = await society_service.update_society_location(db, society_id, location_id, body)
    return SocietyLocationOut.model_validate(location)


@router.post("/{society_id}/structure/flats", response_model=list[PropertyOut])
async def generate_flats_structure(
    society_id: uuid.UUID,
    body: FlatsStructureIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> list[PropertyOut]:
    """Bulk-generates this society's Towers + Flats in one shot — see
    FlatsStructureIn's docstring."""
    properties = await society_service.generate_flats_structure(db, society_id, body)
    return [PropertyOut.model_validate(p) for p in properties]


@router.post("/{society_id}/structure/bungalows", response_model=list[PropertyOut])
async def generate_bungalow_structure(
    society_id: uuid.UUID,
    body: BungalowStructureIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> list[PropertyOut]:
    """Bulk-generates this society's Rows + Houses in one shot — see
    BungalowStructureIn's docstring."""
    properties = await society_service.generate_bungalow_structure(db, society_id, body)
    return [PropertyOut.model_validate(p) for p in properties]


@router.get("/{society_id}/properties", response_model=list[PropertyOut])
async def list_society_properties(
    society_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> list[PropertyOut]:
    """Platform Owner viewing a society's generated houses — mainly so the
    Edit modal can offer the per-house floors_above_ground follow-up step
    after a bulk BUNGALOW generation, and so the Society Mapping page can
    show what's already on record."""
    properties = await property_service.list_properties(db, society_id)
    return [PropertyOut.model_validate(p) for p in properties]


@router.post("/{society_id}/properties", response_model=PropertyOut)
async def add_society_property(
    society_id: uuid.UUID,
    body: PropertyCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> PropertyOut:
    """Platform Owner adding one Property with a specific, hand-typed
    house_number — the Society Mapping page's Flats-mapping step, for a
    Wing/floor combination where the numbering isn't the simple
    sequential scheme the bulk generator assumes."""
    prop = await society_service.add_society_property(db, society_id, body)
    return PropertyOut.model_validate(prop)


@router.patch("/{society_id}/properties/{property_id}/floors", response_model=PropertyOut)
async def update_property_floors(
    society_id: uuid.UUID,
    property_id: uuid.UUID,
    body: PropertyFloorsUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> PropertyOut:
    prop = await society_service.update_property_floors_above_ground(
        db, society_id, property_id, body.floors_above_ground
    )
    return PropertyOut.model_validate(prop)


@router.patch("/{society_id}/status", response_model=SocietyOut)
async def update_status(
    society_id: uuid.UUID,
    body: SocietyStatusUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_OWNER))],
) -> SocietyOut:
    society = await society_service.update_society_status(db, society_id, body.status)
    return SocietyOut.model_validate(society)
