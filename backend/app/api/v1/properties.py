"""
Properties/locations endpoints.

Section 6: Admin has full society access.
Section 7: Sub-admin is scope-restricted — for now, location/property
creation is Admin-only (Section 6 lists this as an Admin capability; Sub-admin
capabilities in Section 7 are Residents/Payments/Complaints/notices within
scope, NOT creating new properties/locations — so write access here stays
Admin-only, read access is open to Admin/Sub-admin/Resident since none of
those roles' read scope is explicitly restricted for this catalog-like data
(house_number/floor/type only — no financial or personal data), the same
"visible to every Resident in the society" pattern already used for
GET /notices and GET /amenities. Sub-admin scope enforcement proper —
filtering to their assigned wing/row — applies to the resident/payment/
complaint endpoints in later modules, not to this general property
directory. GET /properties is also how a Resident's own dashboard resolves
house_number/floor labels for the properties they're linked to (see
frontend hooks/useActiveProperty.ts) — Resident must stay on this list.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.property import (
    PropertyCreateIn,
    PropertyOut,
    PropertyStatusUpdateIn,
    SocietyLocationCreateIn,
    SocietyLocationOut,
)
from app.services import property_service

router = APIRouter(prefix="/properties", tags=["properties"])


@router.post("/locations", response_model=SocietyLocationOut)
async def create_location(
    body: SocietyLocationCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> SocietyLocationOut:
    location = await property_service.create_location(db, current.society_id, body)
    return SocietyLocationOut.model_validate(location)


@router.get("/locations", response_model=list[SocietyLocationOut])
async def list_locations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN))],
) -> list[SocietyLocationOut]:
    locations = await property_service.list_locations(db, current.society_id)
    return [SocietyLocationOut.model_validate(loc) for loc in locations]


@router.post("", response_model=PropertyOut)
async def create_property(
    body: PropertyCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> PropertyOut:
    prop = await property_service.create_property(db, current.society_id, body)
    return PropertyOut.model_validate(prop)


@router.get("", response_model=list[PropertyOut])
async def list_properties(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.RESIDENT))],
) -> list[PropertyOut]:
    properties = await property_service.list_properties(db, current.society_id)
    return [PropertyOut.model_validate(p) for p in properties]


@router.patch("/{property_id}/status", response_model=PropertyOut)
async def update_property_status(
    property_id: uuid.UUID,
    body: PropertyStatusUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> PropertyOut:
    """Audit fix: there was no way to mark a property INACTIVE at all,
    despite the model supporting it and resident_owns_or_rents_property()
    (scope_service) checking it on every Resident-facing action."""
    prop = await property_service.update_property_status(
        db, current.society_id, property_id, body.status.value
    )
    return PropertyOut.model_validate(prop)
