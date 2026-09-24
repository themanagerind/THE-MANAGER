"""Proposal schemas — Section 21/22."""
import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator

from app.models.enums import ProposalScope, ProposalStatus, Vote


class ProposalCreateIn(BaseModel):
    scope_type: ProposalScope
    scope_location_id: uuid.UUID | None = None
    title: str
    description: str

    @model_validator(mode="after")
    def _location_required_unless_society(self) -> "ProposalCreateIn":
        if self.scope_type == ProposalScope.SOCIETY and self.scope_location_id is not None:
            raise ValueError("scope_location_id must be omitted when scope_type=SOCIETY")
        if self.scope_type != ProposalScope.SOCIETY and self.scope_location_id is None:
            raise ValueError("scope_location_id is required when scope_type is WING or ROW")
        return self


class ProposalOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    scope_type: ProposalScope
    scope_location_id: uuid.UUID | None
    title: str
    description: str
    status: ProposalStatus
    created_by: uuid.UUID
    withdrawn_at: datetime | None
    # Who withdrew it — was already written to the DB by withdraw_proposal
    # but never returned to the client, so a withdrawn proposal had no
    # visible record of who ended the vote or when beyond the bare
    # WITHDRAWN status (audit fix, same shape as Payment.approved_by/
    # rejected_by elsewhere in this app).
    withdrawn_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProposalStatusDetailOut(BaseModel):
    """Live threshold snapshot at read time — never cached (Section 49.1)."""

    proposal: ProposalOut
    resident_approve_count: int
    resident_eligible_count: int
    resident_percent: float
    subadmin_approve_count: int
    subadmin_eligible_count: int
    subadmin_percent: float
    resident_threshold_met: bool
    subadmin_threshold_met: bool
    # The CALLER's own current vote (None if they haven't voted yet) — a
    # voter can change their vote until the proposal closes (cast_vote
    # upserts), so the UI needs this to show "you voted APPROVE" rather
    # than leaving the Approve/Reject buttons looking untouched after a
    # vote is cast, which read as "did that even register?" (audit fix).
    my_vote: Vote | None


class CastVoteIn(BaseModel):
    vote: Vote


class VoteOut(BaseModel):
    id: uuid.UUID
    proposal_id: uuid.UUID
    voter_id: uuid.UUID
    vote: Vote
    voted_at: datetime

    model_config = {"from_attributes": True}


class VoteHistoryEntryOut(BaseModel):
    """One row per vote cast/changed (proposal_vote_history — already
    written on every cast_vote call, never exposed until now). Admin/
    Sub-admin oversight only — not returned to plain Residents, who'd
    otherwise see how every neighbor voted."""

    id: uuid.UUID
    voter_name: str
    old_vote: Vote | None
    new_vote: Vote
    changed_at: datetime
