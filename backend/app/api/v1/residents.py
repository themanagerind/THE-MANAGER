"""Residents endpoints — signup, Admin approval, property linking."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role, UserStatus
from app.schemas.resident import (
    AdminSelfResidentLinkIn,
    OwnerContactUpdateIn,
    PropertyLinkRequestDecisionIn,
    PropertyLinkRequestIn,
    PropertyLinkRequestOut,
    PropertyResidentLinkIn,
    PropertyResidentOut,
    ResidentApprovalIn,
    ResidentOut,
    ResidentSignupIn,
)
from app.services import resident_service
from app.services.scope_service import subadmin_has_scope_over_property

router = APIRouter(prefix="/residents", tags=["residents"])


@router.post("/signup", response_model=ResidentOut)
async def signup(
    body: ResidentSignupIn, db: Annotated[AsyncSession, Depends(get_db)]
) -> ResidentOut:
    """Public — no auth required. Resident waits for Admin approval
    (Section 26)."""
    resident = await resident_service.signup_resident(db, body)
    return ResidentOut.model_validate(resident)


@router.get("", response_model=list[ResidentOut])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
    status_filter: Annotated[UserStatus | None, Query(alias="status")] = None,
) -> list[ResidentOut]:
    """Admin's resident directory — e.g. the "Make Sub-admin" picker on
    the Residents page (?status=ACTIVE), separate from list_pending below
    which is specifically the approval queue."""
    residents = await resident_service.list_residents(db, current.society_id, status_filter)
    return [ResidentOut.model_validate(r) for r in residents]


@router.get("/pending", response_model=list[ResidentOut])
async def list_pending(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> list[ResidentOut]:
    residents = await resident_service.list_pending_residents(db, current.society_id)
    return [ResidentOut.model_validate(r) for r in residents]


@router.post("/{resident_id}/approval", response_model=ResidentOut)
async def decide_approval(
    resident_id: uuid.UUID,
    body: ResidentApprovalIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> ResidentOut:
    resident = await resident_service.decide_resident_approval(
        db, current.society_id, resident_id, body.approve, current.user_id
    )
    return ResidentOut.model_validate(resident)


@router.post("/self-link", response_model=PropertyResidentOut)
async def link_self(
    body: AdminSelfResidentLinkIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> PropertyResidentOut:
    """Admin links themselves (not another user) to a property in their own
    society as Owner/Tenant, gaining a RESIDENT role on their existing
    account — no separate approval needed, since the caller already runs
    the society. See resident_service.link_admin_as_resident."""
    link = await resident_service.link_admin_as_resident(db, current.society_id, current.user_id, body)
    return PropertyResidentOut.model_validate(link)


@router.post("/property-links", response_model=PropertyResidentOut)
async def link_property(
    body: PropertyResidentLinkIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> PropertyResidentOut:
    link = await resident_service.link_resident_to_property(db, current.society_id, body)
    return PropertyResidentOut.model_validate(link)


@router.delete("/property-links/{link_id}", response_model=PropertyResidentOut)
async def unlink_property(
    link_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> PropertyResidentOut:
    link = await resident_service.unlink_resident_from_property(db, current.society_id, link_id)
    return PropertyResidentOut.model_validate(link)


@router.patch("/property-links/{link_id}/owner-contact", response_model=PropertyResidentOut)
async def update_owner_contact(
    link_id: uuid.UUID,
    body: OwnerContactUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> PropertyResidentOut:
    """A Tenant self-recording the Owner's contact details on their own
    Profile page — see resident_service.update_owner_contact's docstring
    for why this exists (a Tenant can sign up with no Owner account in
    the system at all)."""
    link = await resident_service.update_owner_contact(db, current.society_id, current.user_id, link_id, body)
    return PropertyResidentOut.model_validate(link)


@router.get("/by-property/{property_id}", response_model=list[PropertyResidentOut])
async def get_property_residents(
    property_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN))],
) -> list[PropertyResidentOut]:
    # Audit fix: a Sub-admin could previously name ANY property in their own
    # society and see its occupants — Wing/Row scope (Section 27) wasn't
    # applied here. Admin has no such restriction.
    if current.active_role == Role.SUB_ADMIN and not await subadmin_has_scope_over_property(
        db, current.user_id, property_id, current.society_id
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This property is outside your assigned scope")
    links = await resident_service.list_property_residents(db, current.society_id, property_id)
    return [PropertyResidentOut.model_validate(link) for link in links]


@router.post("/property-link-requests", response_model=PropertyLinkRequestOut)
async def request_property_link(
    body: PropertyLinkRequestIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> PropertyLinkRequestOut:
    """An already-ACTIVE Resident requesting (from their own Profile page)
    to link themselves to an additional property — stays PENDING until
    the Admin approves it (Section 12/26)."""
    req = await resident_service.submit_property_link_request(db, current.society_id, current.user_id, body)
    return PropertyLinkRequestOut.model_validate(req)


@router.get("/property-link-requests/mine", response_model=list[PropertyLinkRequestOut])
async def my_property_link_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> list[PropertyLinkRequestOut]:
    reqs = await resident_service.list_my_property_link_requests(db, current.society_id, current.user_id)
    return [PropertyLinkRequestOut.model_validate(r) for r in reqs]


@router.get("/property-link-requests/pending", response_model=list[PropertyLinkRequestOut])
async def pending_property_link_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> list[PropertyLinkRequestOut]:
    reqs = await resident_service.list_pending_property_link_requests(db, current.society_id)
    return [PropertyLinkRequestOut.model_validate(r) for r in reqs]


@router.post("/property-link-requests/{request_id}/decision", response_model=PropertyLinkRequestOut)
async def decide_property_link_request(
    request_id: uuid.UUID,
    body: PropertyLinkRequestDecisionIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> PropertyLinkRequestOut:
    req = await resident_service.decide_property_link_request(
        db, current.society_id, request_id, body.approve, body.decision_reason, current.user_id
    )
    return PropertyLinkRequestOut.model_validate(req)


@router.get("/{resident_id}/properties", response_model=list[PropertyResidentOut])
async def get_resident_properties(
    resident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.RESIDENT))],
) -> list[PropertyResidentOut]:
    # A Resident may only query their own properties — not another resident's
    # (private data boundary; Admin has no such restriction here).
    if current.active_role == Role.RESIDENT and resident_id != current.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Residents can only view their own properties")
    links = await resident_service.list_resident_properties(db, current.society_id, resident_id)
    # Audit fix: a Sub-admin could previously query ANY resident's full
    # property list regardless of scope. A resident can be linked to
    # properties across different wings, so filter per-link, not per-request.
    if current.active_role == Role.SUB_ADMIN:
        links = [
            link for link in links
            if await subadmin_has_scope_over_property(db, current.user_id, link.property_id, current.society_id)
        ]
    return [PropertyResidentOut.model_validate(link) for link in links]
