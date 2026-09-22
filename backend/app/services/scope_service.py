"""
Scope resolution — Section 27 (non-negotiable): a Sub-admin's access to a
property must be re-derived from current DB state on every request, never
trusted from the JWT alone. Used by every module where Sub-admin has
scoped (not full-society) access: payments, complaints, notices, etc.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, UserStatus
from app.models.identity import Property, PropertyResident, SubAdminScope, User, UserRole


async def subadmin_has_scope_over_property(
    db: AsyncSession, sub_admin_id: uuid.UUID, property_id: uuid.UUID, society_id: uuid.UUID | None = None
) -> bool:
    """True if `sub_admin_id` currently has an active scope covering the
    wing/row that `property_id` belongs to.

    Defense-in-depth (hardening pass): every current caller already fetches
    `property_id` from a row pre-filtered by `society_id` (e.g. a Payment,
    Complaint, or AmenityBooking looked up via `WHERE society_id = ...`),
    so this was transitively safe. `society_id` is now an explicit optional
    parameter so this function is self-contained and can't silently become
    an IDOR if reused from a context that skips that pre-filter — when
    provided, a property from a different society is rejected outright."""
    prop = (await db.execute(select(Property).where(Property.id == property_id))).scalar_one_or_none()
    if prop is None:
        return False
    if society_id is not None and prop.society_id != society_id:
        return False

    scope = (
        await db.execute(
            select(SubAdminScope).where(
                SubAdminScope.sub_admin_id == sub_admin_id,
                SubAdminScope.location_id == prop.location_id,
                SubAdminScope.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    return scope is not None


async def active_subadmin_ids(db: AsyncSession, society_id: uuid.UUID) -> set[uuid.UUID]:
    """Every currently-active Sub-admin of the society (society-wide,
    scope-independent) — used by both Proposals (80% threshold) and
    Expense Bills (100% threshold), always computed live (Section 49.1/23)."""
    rows = (
        await db.execute(
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .where(
                User.society_id == society_id,
                User.status == UserStatus.ACTIVE,
                UserRole.role == Role.SUB_ADMIN,
                UserRole.revoked_at.is_(None),
            )
        )
    ).scalars().all()
    return set(rows)


async def resident_owns_or_rents_property(
    db: AsyncSession, resident_id: uuid.UUID, property_id: uuid.UUID, society_id: uuid.UUID
) -> bool:
    """Shared authorization check (CRITICAL fix, audit round-8): a Resident
    may only act on a property they're actively linked to (Owner or
    Tenant) — same pattern already used by payment_service for payment
    submission, now extended to complaints, visitors, and amenity bookings,
    which previously only checked society_id and let a Resident name ANY
    property in their own society.

    Audit fix: also requires the property itself to be ACTIVE — an Admin
    marking a property INACTIVE (e.g. under renovation, sold, demolished)
    previously had no effect here; the existing PropertyResident link alone
    kept every Resident-facing action open."""
    prop = (
        await db.execute(
            select(Property).where(Property.id == property_id, Property.society_id == society_id)
        )
    ).scalar_one_or_none()
    if prop is None or prop.status != "ACTIVE":
        return False

    link = (
        await db.execute(
            select(PropertyResident).where(
                PropertyResident.society_id == society_id,
                PropertyResident.resident_id == resident_id,
                PropertyResident.property_id == property_id,
                PropertyResident.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    return link is not None


async def user_has_active_role(
    db: AsyncSession, user_id: uuid.UUID, society_id: uuid.UUID, role: Role
) -> bool:
    """Shared check (HIGH fix, audit round-8): verifies a *target* user (not
    the caller) is ACTIVE, in the right society, and currently holds the
    given role — used wherever one user assigns/targets another by raw ID
    (Sub-admin scope assignment, Manager To-Do assignment) so a mismatched
    or wrong-role user_id is rejected instead of silently accepted (the
    composite FK only guarantees same-society, not correct-role/active)."""
    row = (
        await db.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .where(
                User.id == user_id,
                User.society_id == society_id,
                User.status == UserStatus.ACTIVE,
                UserRole.role == role,
                UserRole.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    return row is not None
