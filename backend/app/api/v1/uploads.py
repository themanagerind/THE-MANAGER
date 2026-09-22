"""File upload endpoints — Section 14.2/14.3 (payment proof)."""
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile

from app.core.security import CurrentUser, require_role
from app.models.enums import Role
from app.schemas.payment import UploadProofOut
from app.services import upload_service

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/payment-proof", response_model=UploadProofOut)
async def upload_payment_proof(
    file: UploadFile,
    current: Annotated[CurrentUser, Depends(require_role(Role.RESIDENT))],
) -> UploadProofOut:
    """Resident uploads a screenshot/receipt photo before submitting a
    manual UPI/Cash payment. Returns a file_url to pass as
    SubmitPaymentIn.proof_file_url — this doesn't create the Payment or
    PaymentProof row itself, submit_payment() does that atomically."""
    file_url = await upload_service.save_payment_proof(file)
    return UploadProofOut(file_url=file_url)
