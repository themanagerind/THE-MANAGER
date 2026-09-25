"""
Governance — Schema Spec v1.3, Section 2.5.

Tables: proposals, proposal_votes, proposal_vote_history, expense_bills,
expense_bill_approvals.

This resolves the forward reference from
account_entries.related_expense_bill_id (app/models/accounts.py).
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import (
    Decision,
    ExpenseBillStatus,
    ProposalScope,
    ProposalStatus,
    Vote,
    VoterRole,
)
from app.models.mixins import CreatedAtOnlyMixin, TimestampMixin, UUIDPKMixin
from app.models.pg_enum import pg_enum


class Proposal(Base, UUIDPKMixin, TimestampMixin):
    """No threshold columns (v1.1 fix) — 90% Resident / 80% Sub-admin are
    hardcoded evaluation rules, not per-row settings. status has exactly 3
    values: OPEN/APPROVED/WITHDRAWN (no auto-expire)."""

    __tablename__ = "proposals"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    scope_type: Mapped[ProposalScope] = mapped_column(
        pg_enum(ProposalScope, "proposal_scope_enum"), nullable=False
    )
    scope_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ProposalStatus] = mapped_column(
        pg_enum(ProposalStatus, "proposal_status_enum"),
        nullable=False,
        default=ProposalStatus.OPEN,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    withdrawn_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "(scope_type = 'SOCIETY' AND scope_location_id IS NULL) OR "
            "(scope_type IN ('WING','ROW') AND scope_location_id IS NOT NULL)",
            name="ck_proposals_scope_location_shape",
        ),
        ForeignKeyConstraint(
            ["society_id", "scope_location_id"],
            ["society_locations.society_id", "society_locations.id"],
            name="fk_proposals_society_scope_location",
        ),
        # NOTE (service-layer, Section 21 zero-eligible rule): creation is
        # blocked if scope has 0 eligible active Residents OR society has 0
        # active Sub-admins — a proposal that can never reach threshold must
        # never be creatable. See app/services/proposal_service.py (Step 3).
    )


class ProposalVote(Base, UUIDPKMixin):
    """Current vote only — one row per voter per proposal, updated in place
    on vote change (Section 22). voter_role is a vote-time context snapshot
    ONLY; live eligibility (for both Resident and Sub-admin tallies) is
    always computed from current role/scope membership, not this column —
    this is what implements the confirmed dual-role rule: a dual-role
    voter's single APPROVE can count toward BOTH thresholds."""

    __tablename__ = "proposal_votes"

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False
    )
    voter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    voter_role: Mapped[VoterRole] = mapped_column(
        pg_enum(VoterRole, "voter_role_enum"), nullable=False
    )
    vote: Mapped[Vote] = mapped_column(pg_enum(Vote, "vote_enum"), nullable=False)
    voted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("proposal_id", "voter_id", name="ux_proposal_votes_one_per_voter"),
    )


class ProposalVoteHistory(Base, UUIDPKMixin):
    """Immutable, insert-only log of every vote cast/changed (Section 22)."""

    __tablename__ = "proposal_vote_history"

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False
    )
    voter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    old_vote: Mapped[Vote | None] = mapped_column(pg_enum(Vote, "vote_enum"), nullable=True)
    new_vote: Mapped[Vote] = mapped_column(pg_enum(Vote, "vote_enum"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Live-denominator + dual-role calculation (Section 49.1, service-level,
    # never a stored/cached percentage):
    #   resident_pct = COUNT(proposal_votes WHERE vote='APPROVE' AND voter is
    #                   CURRENTLY an eligible active Resident in scope)
    #                   / COUNT(currently-eligible active Residents in scope)
    #   subadmin_pct = COUNT(proposal_votes WHERE vote='APPROVE' AND voter is
    #                   CURRENTLY an active Sub-admin of the society)
    #                   / COUNT(currently-active Sub-admins of society)
    # Both queries read the SAME proposal_votes table — no filter on
    # voter_role. See app/services/proposal_service.py (Step 3).


class ExpenseBill(Base, UUIDPKMixin, TimestampMixin):
    """status: DRAFT (Manager draft) -> PENDING_APPROVAL (Admin-finalized) ->
    APPROVED/REJECTED (Section 23).

    Redesign (v1.10, user-requested): approval no longer auto-posts to
    Accounts — see account_entry_service.settle_expense_bill(), which
    Admin drives manually from the Accounts screen, capped at `amount`.
    bill_image_key reverses the old "No proof_url — never required" v1.1
    decision: every new bill must carry a photo of the physical bill,
    enforced at the schema layer (nullable here so pre-existing rows
    aren't retroactively broken — same pattern as AccountEntry.heading_id)."""

    __tablename__ = "expense_bills"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bill_image_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[ExpenseBillStatus] = mapped_column(
        pg_enum(ExpenseBillStatus, "expense_bill_status_enum"),
        nullable=False,
        default=ExpenseBillStatus.DRAFT,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    finalized_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expense_bills_amount_positive"),
        CheckConstraint(
            "status != 'DRAFT' OR finalized_by IS NULL",
            name="ck_expense_bills_draft_no_finalizer",
        ),
        UniqueConstraint("society_id", "id", name="ux_expense_bills_society_id_id"),
        # NOTE (service-layer, Section 23 zero-eligible rule): DRAFT/creation
        # cannot transition to PENDING_APPROVAL if the society currently has
        # 0 active Sub-admins — a 100%-of-zero approval is meaningless.
    )


class ExpenseBillApproval(Base, UUIDPKMixin):
    __tablename__ = "expense_bill_approvals"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    expense_bill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sub_admin_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    decision: Mapped[Decision] = mapped_column(
        pg_enum(Decision, "decision_enum"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "expense_bill_id", "sub_admin_id", name="ux_expense_bill_approvals_once"
        ),
        ForeignKeyConstraint(
            ["society_id", "expense_bill_id"],
            ["expense_bills.society_id", "expense_bills.id"],
            name="fk_expense_bill_approvals_society_bill",
        ),
        ForeignKeyConstraint(
            ["society_id", "sub_admin_id"],
            ["users.society_id", "users.id"],
            name="fk_expense_bill_approvals_society_subadmin",
        ),
        # NOTE (service-layer): reason mandatory if decision='REJECT'.
        # Approval logic: APPROVED when count(APPROVE)==count(currently-active
        # sub-admins of society); REJECTED immediately if count(REJECT)>=1.
        # Reactivation (Section 23 RESOLVED): this row is NEVER deleted when a
        # sub-admin goes inactive — it just stops/starts counting based on
        # their current active status. No re-approval needed on reactivation.
    )
