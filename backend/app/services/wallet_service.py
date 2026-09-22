"""
Wallet service — Section 15 (exactly-once maintenance credit), Section 13.3
(correction adjustments, balance can never go negative — resolved decision).

Concurrency: `get_or_create_wallet` locks the wallet row with `SELECT ...
FOR UPDATE` whenever it's about to be mutated (credit/adjustment), so two
concurrent operations against the same resident's wallet (e.g. an approval
and a correction landing at the same instant) serialize instead of racing
on a read-modify-write of `balance`.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WalletTxnType
from app.models.payments import Wallet, WalletTransaction


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


async def get_wallet(db: AsyncSession, resident_id: uuid.UUID) -> Wallet:
    return await get_or_create_wallet(db, resident_id)
