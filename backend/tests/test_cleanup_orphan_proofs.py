"""scripts/cleanup_orphan_proofs.py — audit finding: an uploaded payment
proof has no PaymentProof row until submit_payment() succeeds, so an
upload the Resident never follows through on sits on disk forever."""
import os
import time
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    HouseType, LocationType, MaintenanceDueStatus, PaymentMethod, PaymentStatus,
    ProofType, RelationshipType, Role, UserStatus,
)
from app.models.identity import Property, PropertyResident, SocietyLocation, User, UserRole
from app.models.payments import MaintenanceDue, Payment, PaymentProof

pytestmark = pytest.mark.asyncio


async def _seed_referenced_proof(db_session: AsyncSession, society_id, storage_key: str) -> None:
    loc = SocietyLocation(society_id=society_id, name="Wing Z", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()
    prop = Property(
        society_id=society_id, location_id=loc.id, house_number="Z-1",
        house_type=HouseType.FLAT, floor_number=1, status="ACTIVE",
    )
    db_session.add(prop)
    await db_session.flush()

    resident = User(society_id=society_id, full_name="Cleanup Test Resident", mobile="9900000001", status=UserStatus.ACTIVE)
    db_session.add(resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    db_session.add(
        PropertyResident(
            society_id=society_id, property_id=prop.id, resident_id=resident.id,
            relationship_type=RelationshipType.OWNER, is_active=True, created_at=datetime.now(timezone.utc),
        )
    )
    await db_session.flush()

    now = datetime.now(timezone.utc)
    due = MaintenanceDue(
        society_id=society_id, property_id=prop.id, amount=1000.0, due_date=now.date(),
        status=MaintenanceDueStatus.PENDING, billing_month=now.date().replace(day=1),
        generated_at=now, updated_at=now,
    )
    db_session.add(due)
    await db_session.flush()

    payment = Payment(
        society_id=society_id, maintenance_due_id=due.id, property_id=prop.id,
        resident_id=resident.id, payment_method=PaymentMethod.MANUAL_UPI, amount=1000.0,
        status=PaymentStatus.PENDING_APPROVAL, idempotency_key=uuid.uuid4(),
    )
    db_session.add(payment)
    await db_session.flush()

    db_session.add(
        PaymentProof(
            payment_id=payment.id, proof_type=ProofType.UPI_SCREENSHOT, file_url=storage_key,
            uploaded_at=now, uploaded_by=resident.id,
        )
    )
    await db_session.commit()


async def test_cleanup_deletes_only_old_unreferenced_files(
    db_session: AsyncSession, two_societies_with_admins, tmp_path, monkeypatch
):
    from scripts import cleanup_orphan_proofs as script

    monkeypatch.setattr(script.settings, "upload_dir", str(tmp_path))
    proof_dir = tmp_path / "payment_proofs"
    proof_dir.mkdir()

    society_id = two_societies_with_admins["a"]["society_id"]

    referenced = proof_dir / "referenced.jpg"
    referenced.write_bytes(b"abc")
    await _seed_referenced_proof(db_session, society_id, "payment_proofs/referenced.jpg")

    orphan_old = proof_dir / "orphan_old.jpg"
    orphan_old.write_bytes(b"xyz")
    old_time = time.time() - 48 * 3600
    os.utime(orphan_old, (old_time, old_time))

    orphan_recent = proof_dir / "orphan_recent.jpg"
    orphan_recent.write_bytes(b"def")

    await script._cleanup(min_age_hours=24, dry_run=False)

    assert referenced.exists()  # referenced — never touched regardless of age
    assert not orphan_old.exists()  # unreferenced and old enough — deleted
    assert orphan_recent.exists()  # unreferenced but too recent — kept


async def test_cleanup_dry_run_deletes_nothing(
    db_session: AsyncSession, two_societies_with_admins, tmp_path, monkeypatch
):
    from scripts import cleanup_orphan_proofs as script

    monkeypatch.setattr(script.settings, "upload_dir", str(tmp_path))
    proof_dir = tmp_path / "payment_proofs"
    proof_dir.mkdir()

    orphan_old = proof_dir / "orphan_old.jpg"
    orphan_old.write_bytes(b"xyz")
    old_time = time.time() - 48 * 3600
    os.utime(orphan_old, (old_time, old_time))

    await script._cleanup(min_age_hours=24, dry_run=True)

    assert orphan_old.exists()
