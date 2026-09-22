"""
Payment proof file uploads — Section 14.2/14.3. Local disk storage under
settings.upload_dir. Swap for S3/GCS in production; callers only see
save_payment_proof() and resolve_payment_proof_path().

Audit fix: files used to be served back by a public StaticFiles mount at
/uploads — anyone with (or guessing) a proof's UUID filename could fetch a
resident's payment screenshot/receipt with no authentication at all. There
is no public mount anymore; the only way to read a file back is
GET /payments/{payment_id}/proofs/{proof_id}/file (app/api/v1/payments.py),
which enforces the same authorization as the proof-listing endpoint before
it streams anything. save_payment_proof() now returns a storage key (not a
URL) — it identifies the file on disk, nothing more; PaymentProof.file_url
stores this key, and the API layer computes the authenticated endpoint
path from it rather than exposing the key itself.
"""
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings

settings = get_settings()

_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

# (content-type, magic-byte signature, extension) — content-type is only a
# hint from the client; the signature is what's actually checked (audit
# fix: previously only file.content_type, a client-supplied header, was
# validated — a malicious client could label any file "image/png").
_SIGNATURES: list[tuple[str, bytes, str]] = [
    ("image/jpeg", b"\xff\xd8\xff", ".jpg"),
    ("image/png", b"\x89PNG\r\n\x1a\n", ".png"),
]


def _detect_image_type(contents: bytes) -> tuple[str, str] | None:
    for content_type, signature, ext in _SIGNATURES:
        if contents.startswith(signature):
            return content_type, ext
    return None


async def save_payment_proof(file: UploadFile) -> str:
    """Validates the file is actually a JPEG or PNG (by signature, not just
    the client-supplied header) and within the size limit, saves it to
    disk, and returns a storage key to pass back as
    SubmitPaymentIn.proof_file_url — NOT a fetchable URL."""
    contents = await file.read()
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"File too large — max {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )
    if len(contents) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")

    detected = _detect_image_type(contents)
    if detected is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only JPEG or PNG images are accepted as payment proof",
        )
    _content_type, ext = detected

    proof_dir = Path(settings.upload_dir) / "payment_proofs"
    proof_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4()}{ext}"
    (proof_dir / filename).write_bytes(contents)

    return f"payment_proofs/{filename}"


def resolve_payment_proof_path(storage_key: str) -> Path:
    """Resolves a PaymentProof.file_url storage key to an on-disk path,
    rejecting anything that would escape settings.upload_dir (defense in
    depth — storage keys are always ones we generated ourselves, but a
    path-traversal check costs nothing)."""
    base = Path(settings.upload_dir).resolve()
    candidate = (base / storage_key).resolve()
    if base not in candidate.parents and candidate != base:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proof file not found")
    if not candidate.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proof file not found")
    return candidate
