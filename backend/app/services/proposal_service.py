"""
Proposal service — Section 21 (thresholds, zero-eligible block), Section 22
(voting, dual-role counting), Section 49.1 (live, never-cached denominator).

Threshold values (90% Resident, 80% Sub-admin) are HARDCODED here per the
v1.1 schema fix — never read from a per-row column (Master Rule: not
configurable, this is a locked business rule).
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProposalScope, ProposalStatus, Role, UserStatus, Vote, VoterRole
from app.models.governance import Proposal, ProposalVote, ProposalVoteHistory
from app.models.identity import Property, PropertyResident, SocietyLocation, User, UserRole
from app.schemas.proposal import ProposalCreateIn
from app.services.scope_service import active_subadmin_ids as _active_subadmin_ids

RESIDENT_THRESHOLD_PERCENT = 90.0
SUBADMIN_THRESHOLD_PERCENT = 80.0


async def _eligible_resident_ids(
    db: AsyncSession, society_id: uuid.UUID, scope_type: ProposalScope, scope_location_id: uuid.UUID | None
) -> set[uuid.UUID]:
    """Currently-active Residents in the proposal's scope — recomputed live,
    never snapshotted (Section 49.1)."""
    base = (
        select(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .where(
            User.society_id == society_id,
            User.status == UserStatus.ACTIVE,
            UserRole.role == Role.RESIDENT,
            UserRole.revoked_at.is_(None),
        )
    )
    if scope_type == ProposalScope.SOCIETY:
        rows = (await db.execute(base)).scalars().all()
        return set(rows)

    scoped = (
        select(PropertyResident.resident_id)
        .join(Property, Property.id == PropertyResident.property_id)
        .where(
            PropertyResident.society_id == society_id,
            PropertyResident.is_active.is_(True),
            Property.location_id == scope_location_id,
        )
    )
    scoped_ids = set((await db.execute(scoped)).scalars().all())
    all_active_residents = set((await db.execute(base)).scalars().all())
    return scoped_ids & all_active_residents


async def create_proposal(
    db: AsyncSession, society_id: uuid.UUID, created_by: uuid.UUID, body: ProposalCreateIn
) -> Proposal:
    if body.scope_type != ProposalScope.SOCIETY:
        location = (
            await db.execute(
                select(SocietyLocation).where(
                    SocietyLocation.id == body.scope_location_id, SocietyLocation.society_id == society_id
                )
            )
        ).scalar_one_or_none()
        if location is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found in this society")

    eligible_residents = await _eligible_resident_ids(
        db, society_id, body.scope_type, body.scope_location_id
    )
    active_subadmins = await _active_subadmin_ids(db, society_id)
    if len(eligible_residents) == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Cannot create proposal — 0 eligible Residents in this scope"
        )
    if len(active_subadmins) == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Cannot create proposal — society has 0 active Sub-admins"
        )

    proposal = Proposal(
        society_id=society_id,
        scope_type=body.scope_type,
        scope_location_id=body.scope_location_id,
        title=body.title,
        description=body.description,
        status=ProposalStatus.OPEN,
        created_by=created_by,
    )
    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)
    return proposal


async def get_proposal(db: AsyncSession, society_id: uuid.UUID, proposal_id: uuid.UUID) -> Proposal:
    proposal = (
        await db.execute(select(Proposal).where(Proposal.id == proposal_id, Proposal.society_id == society_id))
    ).scalar_one_or_none()
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found in this society")
    return proposal


async def list_proposals(db: AsyncSession, society_id: uuid.UUID, skip: int = 0, limit: int = 20) -> tuple[list[Proposal], int]:
    from sqlalchemy import func
    total = (await db.execute(select(func.count()).select_from(Proposal).where(Proposal.society_id == society_id))).scalar_one()
    rows = (
        await db.execute(
            select(Proposal).where(Proposal.society_id == society_id)
            .order_by(Proposal.created_at.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()
    return rows, total


async def compute_status_detail(db: AsyncSession, proposal: Proposal) -> dict:
    """Section 49.1 — live calculation, dual-role counting. A voter's single
    APPROVE counts toward BOTH tallies if they qualify for both. No
    filtering on the stored voter_role snapshot column."""
    eligible_residents = await _eligible_resident_ids(
        db, proposal.society_id, proposal.scope_type, proposal.scope_location_id
    )
    active_subadmins = await _active_subadmin_ids(db, proposal.society_id)

    votes = (
        await db.execute(select(ProposalVote).where(ProposalVote.proposal_id == proposal.id))
    ).scalars().all()
    approve_voter_ids = {v.voter_id for v in votes if v.vote == Vote.APPROVE}

    resident_approve_count = len(approve_voter_ids & eligible_residents)
    subadmin_approve_count = len(approve_voter_ids & active_subadmins)

    resident_pct = (
        (resident_approve_count / len(eligible_residents)) * 100 if eligible_residents else 0.0
    )
    subadmin_pct = (
        (subadmin_approve_count / len(active_subadmins)) * 100 if active_subadmins else 0.0
    )

    return {
        "resident_approve_count": resident_approve_count,
        "resident_eligible_count": len(eligible_residents),
        "resident_percent": round(resident_pct, 2),
        "subadmin_approve_count": subadmin_approve_count,
        "subadmin_eligible_count": len(active_subadmins),
        "subadmin_percent": round(subadmin_pct, 2),
        "resident_threshold_met": resident_pct >= RESIDENT_THRESHOLD_PERCENT,
        "subadmin_threshold_met": subadmin_pct >= SUBADMIN_THRESHOLD_PERCENT,
    }


async def cast_vote(
    db: AsyncSession,
    society_id: uuid.UUID,
    voter_id: uuid.UUID,
    voter_active_role: Role,
    proposal_id: uuid.UUID,
    vote: Vote,
) -> ProposalVote:
    # Row lock (Transactions — proposal voting concurrency): serializes
    # concurrent votes on the same proposal so the threshold re-check below
    # always sees a consistent, up-to-date vote count before deciding
    # whether to flip status to APPROVED.
    proposal = (
        await db.execute(
            select(Proposal)
            .where(Proposal.id == proposal_id, Proposal.society_id == society_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found in this society")
    if proposal.status != ProposalStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Proposal is {proposal.status.value}, voting closed")

    eligible_residents = await _eligible_resident_ids(
        db, society_id, proposal.scope_type, proposal.scope_location_id
    )
    active_subadmins = await _active_subadmin_ids(db, society_id)
    is_eligible_resident = voter_id in eligible_residents
    is_active_subadmin = voter_id in active_subadmins
    if not is_eligible_resident and not is_active_subadmin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not eligible to vote on this proposal")

    stored_role = (
        VoterRole.SUB_ADMIN if voter_active_role == Role.SUB_ADMIN and is_active_subadmin
        else VoterRole.RESIDENT
    )

    now = datetime.now(timezone.utc)
    existing = (
        await db.execute(
            select(ProposalVote).where(ProposalVote.proposal_id == proposal_id, ProposalVote.voter_id == voter_id)
        )
    ).scalar_one_or_none()

    if existing is None:
        vote_row = ProposalVote(
            proposal_id=proposal_id, voter_id=voter_id, voter_role=stored_role, vote=vote, voted_at=now
        )
        db.add(vote_row)
        db.add(
            ProposalVoteHistory(
                proposal_id=proposal_id, voter_id=voter_id, old_vote=None, new_vote=vote, changed_at=now
            )
        )
    else:
        old_vote = existing.vote
        existing.vote = vote
        existing.voted_at = now
        vote_row = existing
        db.add(
            ProposalVoteHistory(
                proposal_id=proposal_id, voter_id=voter_id, old_vote=old_vote, new_vote=vote, changed_at=now
            )
        )

    await db.flush()

    detail = await compute_status_detail(db, proposal)
    if detail["resident_threshold_met"] and detail["subadmin_threshold_met"]:
        proposal.status = ProposalStatus.APPROVED

    await db.commit()
    await db.refresh(vote_row)
    return vote_row


async def withdraw_proposal(
    db: AsyncSession, society_id: uuid.UUID, proposal_id: uuid.UUID, withdrawn_by: uuid.UUID
) -> Proposal:
    proposal = await get_proposal(db, society_id, proposal_id)
    if proposal.status != ProposalStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Proposal is already {proposal.status.value}")
    proposal.status = ProposalStatus.WITHDRAWN
    proposal.withdrawn_by = withdrawn_by
    proposal.withdrawn_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(proposal)
    return proposal
