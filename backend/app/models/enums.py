"""
All PostgreSQL ENUM types used across the schema.
Every value here is traceable to an explicit rule in the Master Requirements —
see FINAL PROMPT Step 1/2. Do not add values without updating the source spec.
"""
import enum


class SocietyStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class UserStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    INACTIVE = "INACTIVE"


class Role(str, enum.Enum):
    PLATFORM_OWNER = "PLATFORM_OWNER"
    ADMIN = "ADMIN"
    SUB_ADMIN = "SUB_ADMIN"
    MANAGER = "MANAGER"
    RESIDENT = "RESIDENT"
    SECURITY_GUARD = "SECURITY_GUARD"


class LocationType(str, enum.Enum):
    WING = "WING"
    ROW = "ROW"


class HouseType(str, enum.Enum):
    FLAT = "FLAT"
    BUNGALOW = "BUNGALOW"


class PropertyStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class RelationshipType(str, enum.Enum):
    OWNER = "OWNER"
    TENANT = "TENANT"


class RoleRequestType(str, enum.Enum):
    SUB_ADMIN_RESIGNATION = "SUB_ADMIN_RESIGNATION"  # only value — Section 49.6


class RoleRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class MaintenanceDueStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"  # exactly 2 values — Section 49.9, no OVERDUE


class PaymentMethod(str, enum.Enum):
    MOCK_ONLINE = "MOCK_ONLINE"
    MANUAL_UPI = "MANUAL_UPI"
    MANUAL_CASH = "MANUAL_CASH"


class PaymentStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    PAID = "PAID"
    REJECTED = "REJECTED"  # exactly 3 values — Section 14, no separate APPROVED


class ProofType(str, enum.Enum):
    UPI_SCREENSHOT = "UPI_SCREENSHOT"
    CASH_RECEIPT = "CASH_RECEIPT"


class PaymentAuditAction(str, enum.Enum):
    CREATED = "CREATED"
    PAID_MARKED = "PAID_MARKED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CORRECTED = "CORRECTED"  # REVERSED removed — v1.1 fix


class WalletTxnType(str, enum.Enum):
    MAINTENANCE_CREDIT = "MAINTENANCE_CREDIT"
    ADJUSTMENT = "ADJUSTMENT"


class EntryType(str, enum.Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class EntrySource(str, enum.Enum):
    MANUAL = "MANUAL"
    MAINTENANCE_PAYMENT = "MAINTENANCE_PAYMENT"
    EXPENSE_BILL = "EXPENSE_BILL"
    ADJUSTMENT = "ADJUSTMENT"


class TodoStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class ComplaintStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class VisitorStatus(str, enum.Enum):
    PRE_APPROVED = "PRE_APPROVED"
    EXPECTED = "EXPECTED"
    ENTERED = "ENTERED"
    EXITED = "EXITED"
    CANCELLED = "CANCELLED"


class BookingStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ProposalScope(str, enum.Enum):
    SOCIETY = "SOCIETY"
    WING = "WING"
    ROW = "ROW"


class ProposalStatus(str, enum.Enum):
    OPEN = "OPEN"
    APPROVED = "APPROVED"
    WITHDRAWN = "WITHDRAWN"  # no auto-EXPIRED — Section 21


class VoterRole(str, enum.Enum):
    RESIDENT = "RESIDENT"
    SUB_ADMIN = "SUB_ADMIN"


class Vote(str, enum.Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class ExpenseBillStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Decision(str, enum.Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class SubscriptionPlatform(str, enum.Enum):
    WEB = "WEB"
    ANDROID = "ANDROID"
    IOS = "IOS"
