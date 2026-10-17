"""
Wallet service — Section 15 (exactly-once maintenance credit), Section 13.3
(correction adjustments, balance can never go negative — resolved decision).

Concurrency: `get_or_create_wallet` locks the wallet row with `SELECT ...
FOR UPDATE` whenever it's about to be mutated (credit/adjustment), so two
concurrent operations against the same resident's wallet (e.g. an approval
and a correction landing at the same instant) serialize instead of racing
on a read-modify-write of `balance`.
"""
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, WalletTxnType
from app.models.identity import User, UserRole
from app.models.payments import Wallet, WalletRedemptionCode, WalletTransaction

# Excludes 0/O and 1/I — a Resident reads this off a screen and types it
# into a store's website, so ambiguous characters cost real support tickets.
_REDEMPTION_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_REDEMPTION_CODE_LENGTH = 8


async def get_or_create_wallet(db: AsyncSession, resident_id: uuid.UUID, *, lock: bool = False) -> Wallet:
    stmt = select(Wallet).where(Wallet.resident_id == resident_id)
    if lock:
        stmt = stmt.with_for_update()
    wallet = (await db.execute(stmt)).scalar_one_or_none()
    if wallet is not None:
        return wallet

    # Row doesn't exist yet — create it. A concurrent first-payment race is
    # still possible here (two inserts for the same brand-new resident); the
    # `UNIQUE(resident_id)` constraint (Schema Spec v1.3) makes the loser
    # fail with IntegrityError rather than silently duplicating a wallet.
    wallet = Wallet(resident_id=resident_id, balance=0)
    db.add(wallet)
    await db.flush()
    return wallet


async def credit_maintenance_payment(
    db: AsyncSession, resident_id: uuid.UUID, payment_id: uuid.UUID, amount: float
) -> WalletTransaction:
    """Exactly-once per payment — relies on the partial unique index
    (wallet_id, payment_id, transaction_type='MAINTENANCE_CREDIT'). Caller
    must be inside the same transaction as the due-status update and ledger
    entry (Section 6, atomic chain)."""
    wallet = await get_or_create_wallet(db, resident_id, lock=True)
    wallet.balance = float(wallet.balance) + amount

    txn = WalletTransaction(
        wallet_id=wallet.id,
        transaction_type=WalletTxnType.MAINTENANCE_CREDIT,
        amount=amount,
        payment_id=payment_id,
        description="Maintenance payment credit",
        created_at=datetime.now(timezone.utc),
    )
    db.add(txn)
    await db.flush()
    return txn


async def apply_adjustment(
    db: AsyncSession, resident_id: uuid.UUID, difference: float, description: str
) -> WalletTransaction:
    """Section 13.3 (RESOLVED): if this adjustment would push balance below
    zero, the whole correction transaction is rejected — never persisted,
    never silently capped. Row-locked so the balance check-then-write can't
    race against a concurrent credit/adjustment on the same wallet."""
    wallet = await get_or_create_wallet(db, resident_id, lock=True)
    new_balance = float(wallet.balance) + difference
    if new_balance < 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot apply correction — insufficient wallet balance "
            f"(current: {wallet.balance}, adjustment: {difference})",
        )
    wallet.balance = new_balance

    txn = WalletTransaction(
        wallet_id=wallet.id,
        transaction_type=WalletTxnType.ADJUSTMENT,
        amount=difference,
        description=description,
        created_at=datetime.now(timezone.utc),
    )
    db.add(txn)
    await db.flush()
    return txn


async def redeem_points(
    db: AsyncSession, resident_id: uuid.UUID, amount: float, description: str, created_by: uuid.UUID
) -> WalletTransaction:
    """Spends `amount` points from the resident's own wallet — the
    ready-made primitive a future Ecom PWA discount redemption will call
    (user-requested; not built yet, so nothing calls this today). Same
    row-locked, balance-can't-go-negative guarantee as apply_adjustment,
    but kept as its own WalletTxnType.REDEMPTION rather than reusing
    ADJUSTMENT, so a resident's own spend is never confused with an
    Admin's correction in the transaction history. Does not touch how
    points are earned — credit_maintenance_payment above is unchanged."""
    if amount <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Redemption amount must be positive")

    wallet = await get_or_create_wallet(db, resident_id, lock=True)
    new_balance = float(wallet.balance) - amount
    if new_balance < 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Insufficient wallet balance (current: {wallet.balance}, requested: {amount})",
        )
    wallet.balance = new_balance

    txn = WalletTransaction(
        wallet_id=wallet.id,
        transaction_type=WalletTxnType.REDEMPTION,
        amount=-amount,
        description=description,
        created_by=created_by,
        created_at=datetime.now(timezone.utc),
    )
    db.add(txn)
    await db.flush()
    return txn


async def get_wallet(db: AsyncSession, resident_id: uuid.UUID) -> Wallet:
    return await get_or_create_wallet(db, resident_id)


async def get_master_wallet(db: AsyncSession, *, lock: bool = False) -> Wallet:
    """The Platform Owner's own Wallet, reused as-is (same table, same
    mechanics — user-requested: no separate Master Wallet system) as
    where a Resident's redeemed points go. Nothing in this codebase caps
    Platform Owner accounts at one (scripts/seed_platform_owner.py can be
    re-run with a different mobile) — rather than hard-failing every
    Resident's redemption if that invariant is ever violated, this
    deterministically picks the earliest-created active Platform Owner
    account, so every call converges on the same one."""
    owner_id = (
        await db.execute(
            select(UserRole.user_id)
            .join(User, User.id == UserRole.user_id)
            .where(UserRole.role == Role.PLATFORM_OWNER, UserRole.revoked_at.is_(None))
            .order_by(User.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if owner_id is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "No Platform Owner account exists for the Master Wallet")
    return await get_or_create_wallet(db, owner_id, lock=lock)


async def _unique_redemption_code(db: AsyncSession) -> str:
    """Pre-checks uniqueness with a SELECT rather than insert-and-catch —
    a caught IntegrityError would need a db.rollback() that undoes the
    debit/credit transfer_to_master_wallet already flushed earlier in
    the same transaction (same reasoning as notification_service's
    dedup pre-check). Collisions are astronomically unlikely (32^8
    codes), so this is a formality, not a real retry loop in practice."""
    for _ in range(5):
        code = "".join(secrets.choice(_REDEMPTION_CODE_ALPHABET) for _ in range(_REDEMPTION_CODE_LENGTH))
        existing = (
            await db.execute(select(WalletRedemptionCode.id).where(WalletRedemptionCode.code == code))
        ).scalar_one_or_none()
        if existing is None:
            return code
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Could not generate a unique redemption code")


async def transfer_to_master_wallet(
    db: AsyncSession, resident_id: uuid.UUID, amount: float
) -> WalletRedemptionCode:
    """A Resident redeems `amount` points into the Platform Owner's
    Master Wallet (user-requested) and gets back a short code — the
    voucher they'll hand to a future, separately-built Ecom store.
    Reuses redeem_points (debit, Resident) and apply_adjustment (credit,
    Master) rather than inventing new wallet mechanics — the code itself
    is the only new thing. Owns its own commit (a single complete
    operation triggered by one API call, same as subadmin_service.
    promote_to_subadmin), unlike the chainable primitives it calls."""
    debit_txn = await redeem_points(
        db, resident_id, amount,
        description="Transferred to Platform Owner Master Wallet", created_by=resident_id,
    )
    # Unlocked read — only .resident_id is used here; apply_adjustment
    # below takes its own row lock when it actually mutates the balance,
    # so locking it twice here would just double the round trips against
    # the single Master Wallet row for no correctness benefit.
    master_wallet = await get_master_wallet(db)
    await apply_adjustment(
        db, master_wallet.resident_id, amount,
        description=f"Received via redemption from resident {resident_id}",
    )

    code = await _unique_redemption_code(db)
    redemption = WalletRedemptionCode(
        resident_id=resident_id, code=code, amount=amount,
        wallet_transaction_id=debit_txn.id, created_at=datetime.now(timezone.utc),
    )
    db.add(redemption)
    await db.commit()
    await db.refresh(redemption)
    return redemption


async def verify_and_redeem_code(
    db: AsyncSession, code: str, request_id: str | None = None
) -> WalletRedemptionCode:
    """The only way a (future) Ecom store's backend confirms a code is
    valid — row-locked so two near-simultaneous verify calls for the
    same code (e.g. a client retry) can't both succeed. Normalizes case/
    whitespace before matching — codes are generated uppercase-only
    (_REDEMPTION_CODE_ALPHABET), but there's no guarantee a store's own
    checkout UI preserves that by the time it POSTs here.

    Idempotency (user-reported gap): THE-MANAGER can mark a code used and
    commit, then lose the response to a network failure before the store
    sees it — a bare retry would get 409 with no way to tell "my own
    unseen success" apart from "someone else already spent this code."
    `request_id` is the store's own idempotency key for *this specific
    redemption attempt*; a retry that repeats the same request_id against
    an already-used code replays the original success rather than 409.
    Any other request_id (including none) against a used code is treated
    as a genuine reuse attempt and still gets 409 — so a code can only
    ever be effectively spent once no matter how it's retried."""
    code = code.strip().upper()
    redemption = (
        await db.execute(
            select(WalletRedemptionCode).where(WalletRedemptionCode.code == code).with_for_update()
        )
    ).scalar_one_or_none()
    if redemption is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Redemption code not found")
    if redemption.is_used:
        if request_id and redemption.consumed_request_id == request_id:
            return redemption
        raise HTTPException(status.HTTP_409_CONFLICT, "Redemption code has already been used")

    redemption.is_used = True
    redemption.used_at = datetime.now(timezone.utc)
    redemption.consumed_request_id = request_id
    await db.commit()
    await db.refresh(redemption)
    return redemption


async def list_redemption_codes(
    db: AsyncSession, resident_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> tuple[list[WalletRedemptionCode], int]:
    total = (
        await db.execute(
            select(func.count()).select_from(WalletRedemptionCode).where(
                WalletRedemptionCode.resident_id == resident_id
            )
        )
    ).scalar_one()
    rows = (
        await db.execute(
            select(WalletRedemptionCode).where(WalletRedemptionCode.resident_id == resident_id)
            .order_by(WalletRedemptionCode.created_at.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()
    return rows, total
