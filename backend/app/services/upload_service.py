"""
Payment proof file uploads — Section 14.2/14.3. Local disk storage under
settings.upload_dir, served back by main.py's StaticFiles mount at
/uploads. Swap for S3/GCS in production; callers only see save_payment_proof().
"""
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings

settings = get_settings()

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
_EXT_BY_CONTENT_TYPE = {"image/jpeg": ".jpg", "image/png": ".png"}


async def save_payment_proof(file: UploadFile) -> str:
    """Validates content-type and size, saves to disk, returns a URL path
    (e.g. "/uploads/payment_proofs/<uuid>.jpg") to pass back as
    SubmitPaymentIn.proof_file_url."""
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only JPEG or PNG images are accepted as payment proof",
        )

    contents = await file.read()
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"File too large — max {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )
    if len(contents) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")

    proof_dir = Path(settings.upload_dir) / "payment_proofs"
    proof_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4()}{_EXT_BY_CONTENT_TYPE[file.content_type]}"
    (proof_dir / filename).write_bytes(contents)

    return f"/uploads/payment_proofs/{filename}"
