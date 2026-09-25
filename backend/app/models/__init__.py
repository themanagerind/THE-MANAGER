"""
ORM model registry. Import every model module here so Alembic's
autogenerate (target_metadata) can discover all tables via Base.metadata.

Progress (FINAL PROMPT Step 2 groups, being added one-by-one):
  [x] Identity & Structure  -> identity.py
  [x] Payments & Wallet     -> payments.py
  [x] Accounts / Ledger     -> accounts.py
  [x] Manager & Operations  -> operations.py
  [x] Governance            -> governance.py
  [x] Notifications infra   -> notifications.py

ALL 32 TABLES COMPLETE — matches FINAL PROMPT Step 2 (DB Schema v1.3) exactly.
"""
from app.models.identity import (  # noqa: F401
    Property,
    PropertyResident,
    RoleRequest,
    Society,
    SocietyLocation,
    SubAdminScope,
    User,
    UserRole,
)
from app.models.payments import (  # noqa: F401
    MaintenanceDue,
    Payment,
    PaymentAuditLog,
    PaymentCorrection,
    PaymentProof,
    Wallet,
    WalletTransaction,
)
from app.models.accounts import AccountEntry, AccountEntryEditHistory  # noqa: F401
from app.models.operations import (  # noqa: F401
    Amenity,
    AmenityBooking,
    Complaint,
    ComplaintAssignment,
    ManagerDailyTask,
    ManagerTodo,
    Notice,
    TaskSuggestion,
    Visitor,
    VisitorLog,
)
from app.models.governance import (  # noqa: F401
    ExpenseBill,
    ExpenseBillApproval,
    Proposal,
    ProposalVote,
    ProposalVoteHistory,
)
from app.models.notifications import PushSubscription  # noqa: F401
