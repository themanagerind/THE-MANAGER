"""
Payments & Wallet — Schema Spec v1.3, Section 2.2.

Tables: maintenance_dues, payments, payment_proofs, payment_audit_logs,
payment_corrections, wallets, wallet_transactions.

payment_corrections.ledger_adjustment_entry_id references account_entries,
defined in app/models/accounts.py (Group 3) — string FK ref, resolved lazily
by SQLAlchemy; both modules must be imported before Base.metadata is used
for DDL (see app/models/__init__.py).
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import (
    MaintenanceDueStatus,
    PaymentAuditAction,
    PaymentMethod,
    PaymentStatus,
    ProofType,
    WalletTxnType,
)
from app.models.mixins import CreatedAtOnlyMixin, TimestampMixin, UUIDPKMixin
from app.models.pg_enum import pg_enum


class MaintenanceDue(Base, UUIDPKMixin):
    __tablename__ = "maintenance_dues"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[MaintenanceDueStatus] = mapped_column(
        pg_enum(MaintenanceDueStatus, "maintenance_due_status_enum"),
        nullable=False,
        default=MaintenanceDueStatus.PENDING,
    )
    # v1.1 fix: mandatory billing_month replaces nullable period_start/period_end,
    # which could not actually enforce monthly uniqueness in Postgres.
    billing_month: Mapped[date] = mapped_column(Date, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Late-payment penalty — opt-in per bill generation (never on by
    # default), a fixed amount added per day once due_date has passed.
    # penalty_per_day is only ever set alongside penalty_enabled=True
    # (service-layer validated, not a DB constraint — same reasoning as
    # AdminChangeRequestIn's new_admin_user_id XOR manual fields).
    # Accrued penalty is computed on read (maintenance_service.
    # compute_penalty), never stored as a running total — this app has
    # no in-app scheduler to accumulate one against.
    penalty_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    penalty_per_day: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Admin can forgive an already-enabled penalty for this specific due
    # at any time — accrual stops growing from that point on (compute_penalty
    # always returns 0 once waived, regardless of how overdue it still is).
    penalty_waived: Mapped[bool] = mapped_column(nullable=False, default=False)
    penalty_waived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    penalty_waived_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_maintenance_dues_amount_nonneg"),
        CheckConstraint(
            "penalty_per_day IS NULL OR penalty_per_day >= 0", name="ck_maintenance_dues_penalty_per_day_nonneg"
        ),
        # 1 bill per property per month — DB-enforced (Schema Spec v1.1 fix #1)
        UniqueConstraint(
            "society_id", "property_id", "billing_month", name="ux_maintenance_due_month"
        ),
        UniqueConstraint("society_id", "id", name="ux_maintenance_dues_society_id_id"),
        ForeignKeyConstraint(
            ["society_id", "property_id"],
            ["properties.society_id", "properties.id"],
            name="fk_maintenance_dues_society_property",
        ),
    )


class Payment(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "payments"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    maintenance_due_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        pg_enum(PaymentMethod, "payment_method_enum"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    # How much of `amount` above was a late-payment penalty, folded in at
    # submission time (payment_service.submission, from maintenance_service.
    # compute_penalty against the due as of that moment) — 0 for a due with
    # no penalty enabled/accrued. Kept separate from `amount` purely for
    # transparency on the resident's payment history/receipt.
    penalty_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    # exactly 3 values, no separate APPROVED (Section 14 resolution)
    status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus, "payment_status_enum"),
        nullable=False,
        default=PaymentStatus.PENDING_APPROVAL,
    )
    reference_number: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # offline background-sync dedupe key (Section 37)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    paid_marked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # approved_* = metadata on the PAID row (who/when approved a manual payment)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        CheckConstraint("penalty_amount >= 0", name="ck_payments_penalty_amount_nonneg"),
        UniqueConstraint(
            "maintenance_due_id", "idempotency_key", name="ux_payments_due_idempotency"
        ),
        # at most one unresolved payment per due at a time (Section 49.2)
        Index(
            "ux_payments_one_pending_per_due",
            "maintenance_due_id",
            unique=True,
            postgresql_where="status = 'PENDING_APPROVAL'",
        ),
        ForeignKeyConstraint(
            ["society_id", "property_id"],
            ["properties.society_id", "properties.id"],
            name="fk_payments_society_property",
        ),
        ForeignKeyConstraint(
            ["society_id", "resident_id"],
            ["users.society_id", "users.id"],
            name="fk_payments_society_resident",
        ),
        ForeignKeyConstraint(
            ["society_id", "maintenance_due_id"],
            ["maintenance_dues.society_id", "maintenance_dues.id"],
            name="fk_payments_society_due",
        ),
        # NOTE (service-layer, cross-table, not a plain CHECK):
        #  - MANUAL_UPI/MANUAL_CASH payments cannot reach PENDING_APPROVAL without
        #    >=1 payment_proofs row (create proof(s) + payment in one transaction).
        #  - Active-resident payment authorization: resident_id must have an active
        #    property_residents row for property_id, an active RESIDENT role, and
        #    all three (resident/property/due) must resolve to the same society_id.
        #  See app/services/payment_service.py (Step 3).
    )


class PaymentProof(Base, UUIDPKMixin):
    __tablename__ = "payment_proofs"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False
    )
    proof_type: Mapped[ProofType] = mapped_column(
        pg_enum(ProofType, "proof_type_enum"), nullable=False
    )
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )


class PaymentAuditLog(Base, UUIDPKMixin, CreatedAtOnlyMixin):
    """Immutable — INSERT/SELECT only. Grant no UPDATE/DELETE to the app DB role
    for this table in production (Section 38 / Schema Spec Sec 10)."""

    __tablename__ = "payment_audit_logs"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False
    )
    action: Mapped[PaymentAuditAction] = mapped_column(
        pg_enum(PaymentAuditAction, "payment_audit_action_enum"), nullable=False
    )
    old_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    old_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    new_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )


class PaymentCorrection(Base, UUIDPKMixin):
    __tablename__ = "payment_corrections"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False
    )
    old_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    new_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    difference: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    corrected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    wallet_adjustment_txn_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallet_transactions.id"), nullable=True
    )
    ledger_adjustment_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account_entries.id"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "difference = new_amount - old_amount", name="ck_payment_corrections_diff"
        ),
        # each adjustment row belongs to exactly one correction (audit item G)
        Index(
            "ux_payment_corrections_wallet_txn",
            "wallet_adjustment_txn_id",
            unique=True,
            postgresql_where="wallet_adjustment_txn_id IS NOT NULL",
        ),
        Index(
            "ux_payment_corrections_ledger_entry",
            "ledger_adjustment_entry_id",
            unique=True,
            postgresql_where="ledger_adjustment_entry_id IS NOT NULL",
        ),
        # NOTE: only applicable to payments.status='PAID' — service-level check.
        # Wallet-balance-would-go-negative -> the whole correction transaction is
        # rejected by the service layer (Q&A resolution, never allowed to persist).
    )


class Wallet(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "wallets"

    resident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True
    )
    balance: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_wallets_balance_nonneg"),
    )


class WalletTransaction(Base, UUIDPKMixin, CreatedAtOnlyMixin):
    __tablename__ = "wallet_transactions"

    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False
    )
    transaction_type: Mapped[WalletTxnType] = mapped_column(
        pg_enum(WalletTxnType, "wallet_txn_type_enum"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        # exactly-once maintenance credit per payment (Section 15/17)
        Index(
            "ux_wallet_txn_maintenance_credit_once",
            "wallet_id",
            "payment_id",
            "transaction_type",
            unique=True,
            postgresql_where="transaction_type = 'MAINTENANCE_CREDIT'",
        ),
    )
