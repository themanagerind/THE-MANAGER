"""
Payment service — Section 14 (payment lifecycle), Section 49.2 (one pending
payment per due), Section 6 (atomic payment->wallet->ledger chain),
Section 13.3/49.3 (correction event model).

Split into one module per responsibility (submission, approval, rejection,
correction, the shared atomic finalize step, and read-only queries) —
this file is the public facade so every existing caller
(`from app.services import payment_service`, `payment_service.submit_payment(...)`)
keeps working unchanged.
"""
from app.services.payment_service.approval import approve_payment
from app.services.payment_service.correction import correct_payment
from app.services.payment_service.queries import list_payments_for_society, list_pending_payments
from app.services.payment_service.rejection import reject_payment
from app.services.payment_service.submission import submit_payment

__all__ = [
    "submit_payment",
    "approve_payment",
    "reject_payment",
    "correct_payment",
    "list_payments_for_society",
    "list_pending_payments",
]
