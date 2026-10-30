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

Audit fix: no per-user rate limit or storage cap existed — an
authenticated Resident could upload arbitrarily many 5 MB files. Added a
Redis-based per-user hourly cap (same pattern as otp_service/
resident_service's signup rate limit) and a total-storage cap checked
before every write.

Audit fix (orphaned uploads): a file saved here has no PaymentProof row
until submit_payment() actually succeeds with this storage key — if the
Resident uploads and then never submits the payment, the file sits on
disk forever with nothing referencing it. scripts/cleanup_orphan_proofs.py
finds and deletes files older than a threshold with no matching
PaymentProof.file_url; run it periodically (cron), same pattern as
scripts/seed_platform_owner.py — there's no in-app scheduler to hang a
periodic job off of.
"""
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.redis_client import get_redis

settings = get_settings()

_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
_MAX_UPLOADS_PER_HOUR = 20
_UPLOAD_RATE_WINDOW_SECONDS = 3600
_MAX_TOTAL_STORAGE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB


def _upload_rate_key(uploaded_by: uuid.UUID) -> str:
    return f"payment_proof_upload:rate:{uploaded_by}"


def _current_storage_bytes() -> int:
    proof_dir = Path(settings.upload_dir) / "payment_proofs"
    if not proof_dir.exists():
        return 0
    return sum(f.stat().st_size for f in proof_dir.iterdir() if f.is_file())

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


async def save_payment_proof(file: UploadFile, uploaded_by: uuid.UUID) -> str:
    """Validates the file is actually a JPEG or PNG (by signature, not just
    the client-supplied header) and within the size limit, saves it to
    disk, and returns a storage key to pass back as
    SubmitPaymentIn.proof_file_url — NOT a fetchable URL."""
    r = get_redis()
    attempts = await r.incr(_upload_rate_key(uploaded_by))
    if attempts == 1:
        await r.expire(_upload_rate_key(uploaded_by), _UPLOAD_RATE_WINDOW_SECONDS)
    if attempts > _MAX_UPLOADS_PER_HOUR:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many uploads — try again in an hour"
        )

    contents = await file.read()
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"File too large — max {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )
    if len(contents) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")

    if _current_storage_bytes() + len(contents) > _MAX_TOTAL_STORAGE_BYTES:
        # Not the uploader's fault — flag it distinctly from their own bad
        # input so an ops alert can tell the difference from a 400.
        raise HTTPException(
            status.HTTP_507_INSUFFICIENT_STORAGE,
            "Storage is full — contact support",
        )

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


# --- Profile photo (avatar) uploads — Resident/Admin/Sub-admin self-service,
# same local-disk pattern as payment proofs but smaller, and with the old
# file deleted synchronously on replace/remove (there's exactly one avatar
# per user at a time, so no orphan-cleanup script is needed here). ---

_MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2 MB
_MAX_AVATAR_UPLOADS_PER_HOUR = 10


def _avatar_rate_key(user_id: uuid.UUID) -> str:
    return f"avatar_upload:rate:{user_id}"


async def save_user_avatar(file: UploadFile, user_id: uuid.UUID) -> str:
    """Validates the file is actually a JPEG or PNG (by signature) and
    within the size limit, saves it to disk, and returns a storage key to
    store as User.avatar_key — NOT a fetchable URL."""
    r = get_redis()
    attempts = await r.incr(_avatar_rate_key(user_id))
    if attempts == 1:
        await r.expire(_avatar_rate_key(user_id), _UPLOAD_RATE_WINDOW_SECONDS)
    if attempts > _MAX_AVATAR_UPLOADS_PER_HOUR:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many uploads — try again in an hour"
        )

    contents = await file.read()
    if len(contents) > _MAX_AVATAR_BYTES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"File too large — max {_MAX_AVATAR_BYTES // (1024 * 1024)} MB",
        )
    if len(contents) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")

    detected = _detect_image_type(contents)
    if detected is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only JPEG or PNG images are accepted as a profile photo",
        )
    _content_type, ext = detected

    avatar_dir = Path(settings.upload_dir) / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4()}{ext}"
    (avatar_dir / filename).write_bytes(contents)

    return f"avatars/{filename}"


def resolve_avatar_path(storage_key: str) -> Path:
    """Same path-traversal-safe resolution as resolve_payment_proof_path,
    scoped to avatar storage keys."""
    base = Path(settings.upload_dir).resolve()
    candidate = (base / storage_key).resolve()
    if base not in candidate.parents and candidate != base:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    if not candidate.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    return candidate


def delete_avatar_file(storage_key: str) -> None:
    """Best-effort delete of a previous avatar file when it's replaced or
    removed — ignores a missing file rather than raising, since the DB
    row being updated is what actually matters."""
    try:
        path = resolve_avatar_path(storage_key)
    except HTTPException:
        return
    path.unlink(missing_ok=True)


# --- Expense bill image uploads — every new ExpenseBill must carry a photo
# of the physical bill/receipt (user-requested redesign). Same local-disk,
# storage-key, magic-byte-validated, rate-limited pattern as payment
# proofs above; retrieval is GET /expense-bills/{bill_id}/image, checked
# with the same authorization as the bill itself before streaming. ---


def _bill_image_rate_key(uploaded_by: uuid.UUID) -> str:
    return f"expense_bill_image_upload:rate:{uploaded_by}"


async def save_expense_bill_image(file: UploadFile, uploaded_by: uuid.UUID) -> str:
    """Validates the file is actually a JPEG or PNG (by signature) and
    within the size limit, saves it to disk, and returns a storage key to
    pass back as ExpenseBillCreateIn.bill_image_key — NOT a fetchable URL."""
    r = get_redis()
    attempts = await r.incr(_bill_image_rate_key(uploaded_by))
    if attempts == 1:
        await r.expire(_bill_image_rate_key(uploaded_by), _UPLOAD_RATE_WINDOW_SECONDS)
    if attempts > _MAX_UPLOADS_PER_HOUR:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many uploads — try again in an hour"
        )

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
            "Only JPEG or PNG images are accepted as a bill image",
        )
    _content_type, ext = detected

    bill_image_dir = Path(settings.upload_dir) / "expense_bill_proofs"
    bill_image_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4()}{ext}"
    (bill_image_dir / filename).write_bytes(contents)

    return f"expense_bill_proofs/{filename}"


def resolve_expense_bill_image_path(storage_key: str) -> Path:
    """Same path-traversal-safe resolution as resolve_payment_proof_path,
    scoped to expense bill image storage keys."""
    base = Path(settings.upload_dir).resolve()
    candidate = (base / storage_key).resolve()
    if base not in candidate.parents and candidate != base:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bill image not found")
    if not candidate.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bill image not found")
    return candidate
