"""Proposals endpoints — Section 21/22."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.pagination import Page, Pagination, pagination_params
from app.schemas.proposal import (
    CastVoteIn,
    ProposalCreateIn,
    ProposalOut,
    ProposalStatusDetailOut,
    VoteHistoryEntryOut,
    VoteOut,
)
from app.services import proposal_service

router = APIRouter(prefix="/proposals", tags=["proposals"])


@router.post("", response_model=ProposalOut)
async def create(
    body: ProposalCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> ProposalOut:
    proposal = await proposal_service.create_proposal(db, current.society_id, current.user_id, body)
    return ProposalOut.model_validate(proposal)


@router.get("", response_model=Page[ProposalOut])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[
        CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.RESIDENT))
    ],
    pagination: Annotated[Pagination, Depends(pagination_params)],
) -> Page[ProposalOut]:
    proposals, total = await proposal_service.list_proposals(db, current.society_id, pagination.skip, pagination.limit)
    return Page(items=[ProposalOut.model_validate(p) for p in proposals], total=total, skip=pagination.skip, limit=pagination.limit)


@router.get("/{proposal_id}", response_model=ProposalStatusDetailOut)
async def get_detail(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[
        CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN, Role.RESIDENT))
    ],
) -> ProposalStatusDetailOut:
    proposal = await proposal_service.get_proposal(db, current.society_id, proposal_id)
    detail = await proposal_service.compute_status_detail(db, proposal)
    my_vote = await proposal_service.get_my_vote(db, proposal_id, current.user_id)
    return ProposalStatusDetailOut(proposal=ProposalOut.model_validate(proposal), my_vote=my_vote, **detail)


@router.get("/{proposal_id}/history", response_model=list[VoteHistoryEntryOut])
async def get_vote_history(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN, Role.SUB_ADMIN))],
) -> list[VoteHistoryEntryOut]:
    """Admin/Sub-admin oversight only — every vote cast/changed on this
    proposal, newest first. Not exposed to plain Residents, who'd
    otherwise see how every neighbor voted."""
    await proposal_service.get_proposal(db, current.society_id, proposal_id)
    history = await proposal_service.list_vote_history(db, proposal_id)
    return [VoteHistoryEntryOut(**h) for h in history]


@router.post("/{proposal_id}/vote", response_model=VoteOut)
async def vote(
    proposal_id: uuid.UUID,
    body: CastVoteIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.SUB_ADMIN, Role.RESIDENT))],
) -> VoteOut:
    vote_row = await proposal_service.cast_vote(
        db, current.society_id, current.user_id, current.active_role, proposal_id, body.vote
    )
    return VoteOut.model_validate(vote_row)


@router.post("/{proposal_id}/withdraw", response_model=ProposalOut)
async def withdraw(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[CurrentUser, Depends(require_role(Role.ADMIN))],
) -> ProposalOut:
    proposal = await proposal_service.withdraw_proposal(db, current.society_id, proposal_id, current.user_id)
    return ProposalOut.model_validate(proposal)
