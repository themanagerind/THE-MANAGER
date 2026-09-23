"""
Identity & Structure — Schema Spec v1.3, Section 2.1.

Tables: societies, users, user_roles, society_locations, properties,
property_residents, sub_admin_scopes, role_requests.

Every constraint here is traced to a spec line in a comment. Do not add,
remove, or loosen a constraint without updating the FINAL PROMPT spec first.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import (
    HouseType,
    LocationType,
    RelationshipType,
    Role,
    RoleRequestStatus,
    RoleRequestType,
    SocietyStatus,
    UserStatus,
)
from app.models.mixins import TimestampMixin, UUIDPKMixin
from app.models.pg_enum import pg_enum


class Society(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "societies"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    status: Mapped[SocietyStatus] = mapped_column(
        pg_enum(SocietyStatus, "society_status_enum"),
        nullable=False,
        default=SocietyStatus.PENDING,
    )
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # v1.4 addition — GPS pin for the society, entered as plain lat/long
    # (Platform Owner copies it from Google Maps etc.), the one field
    # that stays optional on both create and edit — see SocietyCreateIn/
    # SocietyUpdateIn docstrings. Always both-or-neither: enforced by the
    # CHECK below since a lone coordinate is meaningless.
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name="ck_societies_gps_both_or_neither",
        ),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_societies_latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_societies_longitude_range",
        ),
    )

    users: Mapped[list["User"]] = relationship(back_populates="society")


class User(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "users"

    # NOT NULL except Platform Owner rows (Section 2.1 / Step1 Section 2.1).
    # society_id is immutable post-creation (v1.3 — no cross-society move workflow).
    society_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    mobile: Mapped[str] = mapped_column(String(15), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # password_hash intentionally does NOT exist — Mobile+OTP only, v1.1 fix.
    status: Mapped[UserStatus] = mapped_column(
        pg_enum(UserStatus, "user_status_enum"),
        nullable=False,
        default=UserStatus.PENDING,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    society: Mapped["Society | None"] = relationship(back_populates="users")
    roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user", foreign_keys="UserRole.user_id"
    )

    __table_args__ = (
        # mobile unique per society (not globally) — identity model, Step1 Sec 2.1
        Index(
            "ux_users_society_mobile",
            "society_id",
            "mobile",
            unique=True,
            postgresql_where="society_id IS NOT NULL",
        ),
        # Platform Owner rows: mobile globally unique among themselves —
        # genuine partial unique index, confirmed correct (Schema Spec audit item C)
        Index(
            "ux_users_platform_owner_mobile",
            "mobile",
            unique=True,
            postgresql_where="society_id IS NULL",
        ),
        # UNIQUE(society_id, id) — v1.3 addition, required by every composite FK
        # elsewhere in the schema that references users(society_id, id)
        UniqueConstraint("society_id", "id", name="ux_users_society_id_id"),
    )


class UserRole(Base, UUIDPKMixin):
    """Dual-role model — Section 3/4: ADMIN+RESIDENT, SUB_ADMIN+RESIDENT etc."""

    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    role: Mapped[Role] = mapped_column(pg_enum(Role, "role_enum"), nullable=False)
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(
        back_populates="roles", foreign_keys=[user_id]
    )

    __table_args__ = (
        # a user can't hold the same role twice concurrently, but CAN hold
        # ADMIN + RESIDENT simultaneously (different role values) — dual-role core
        Index(
            "ux_user_roles_active",
            "user_id",
            "role",
            unique=True,
            postgresql_where="revoked_at IS NULL",
        ),
    )
    # role='PLATFORM_OWNER' only assignable where users.society_id IS NULL;
    # every other role requires users.society_id IS NOT NULL.
    # RESOLVED (audit round-8 item 7): enforced by a real DB trigger —
    # alembic/versions/0002_role_society_trigger.py — not just service code.


class SocietyLocation(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "society_locations"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location_type: Mapped[LocationType] = mapped_column(
        pg_enum(LocationType, "location_type_enum"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "society_id", "location_type", "name", name="ux_location_society_type_name"
        ),
        # v1.3 addition — supports composite FKs from properties, sub_admin_scopes, etc.
        UniqueConstraint("society_id", "id", name="ux_society_locations_society_id_id"),
    )


class Property(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "properties"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    house_number: Mapped[str] = mapped_column(String(50), nullable=False)
    house_type: Mapped[HouseType] = mapped_column(
        pg_enum(HouseType, "house_type_enum"), nullable=False
    )
    # mandatory if FLAT, optional if BUNGALOW — enforced by CHECK below
    floor_number: Mapped[int | None] = mapped_column(nullable=True)
    # v1.4 addition — BUNGALOW-only: a house's ground floor is always
    # implied (0 here just means "ground floor only"); this counts any
    # additional storeys built above it. Always 0 for FLAT (a flat's own
    # storey is floor_number above) — enforced by CHECK below. Set via
    # society_service.update_property_floors_above_ground, normally after
    # a bulk generate_bungalow_structure() call that starts every house
    # at 0 (Section: Platform Owner bulk structure generation).
    floors_above_ground: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ACTIVE"
    )

    __table_args__ = (
        CheckConstraint(
            "house_type != 'FLAT' OR floor_number IS NOT NULL",
            name="ck_properties_flat_requires_floor",
        ),
        CheckConstraint(
            "house_type = 'BUNGALOW' OR floors_above_ground = 0",
            name="ck_properties_floors_above_ground_bungalow_only",
        ),
        UniqueConstraint("society_id", "house_number", name="ux_properties_society_house"),
        UniqueConstraint("society_id", "id", name="ux_properties_society_id_id"),
        # Composite FK for tenant isolation (Schema Spec Sec 3):
        # rejects a property pointing at a location belonging to a different society.
        ForeignKeyConstraint(
            ["society_id", "location_id"],
            ["society_locations.society_id", "society_locations.id"],
            name="fk_properties_society_location",
        ),
        # NOTE: location_type-vs-house_type match (FLAT->WING, BUNGALOW->ROW) is a
        # cross-table rule — enforced via BEFORE INSERT/UPDATE trigger (Step 3),
        # not expressible as a single-table CHECK. See Schema Spec Sec 2.1 `properties`.
    )


class PropertyResident(Base, UUIDPKMixin):
    __tablename__ = "property_residents"

    # denormalized society_id — v1.1 fix, required for composite-FK tenant isolation
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    relationship_type: Mapped[RelationshipType] = mapped_column(
        pg_enum(RelationshipType, "relationship_type_enum"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index(
            "ux_property_residents_active",
            "property_id",
            "resident_id",
            "relationship_type",
            unique=True,
            postgresql_where="is_active = true",
        ),
        ForeignKeyConstraint(
            ["society_id", "property_id"],
            ["properties.society_id", "properties.id"],
            name="fk_property_residents_society_property",
        ),
        ForeignKeyConstraint(
            ["society_id", "resident_id"],
            ["users.society_id", "users.id"],
            name="fk_property_residents_society_resident",
        ),
        # NOTE (trigger, cross-row — not a plain CHECK): a TENANT row can only be
        # is_active=TRUE if at least one OWNER row for the same property_id is
        # also is_active=TRUE. See Step 3 service/trigger implementation.
        # Never hard-delete — use end_date + is_active=FALSE instead.
    )


class PropertyLinkRequest(Base, UUIDPKMixin):
    """v1.5 addition — an already-ACTIVE Resident requesting to link
    themselves to an (additional) property from their own Profile page.
    Unlike the signup-time link (created immediately, inert until account
    approval) and the Admin-driven property-links endpoint (immediate,
    no approval needed — the Admin already runs the society), THIS path
    is Resident-initiated after the fact, so it stays PENDING until the
    Admin reviews it; approving it is what actually creates the real
    PropertyResident row (resident_service.decide_property_link_request),
    same "approval materializes the record" pattern as Resident/Admin
    signup approval."""

    __tablename__ = "property_link_requests"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    relationship_type: Mapped[RelationshipType] = mapped_column(
        pg_enum(RelationshipType, "relationship_type_enum"), nullable=False
    )
    status: Mapped[RoleRequestStatus] = mapped_column(
        pg_enum(RoleRequestStatus, "role_request_status_enum"),
        nullable=False,
        default=RoleRequestStatus.PENDING,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        # A resident can't spam multiple pending requests for the same
        # property — service layer also checks this (clean error before
        # hitting this constraint), same pattern as submit_resignation's
        # existing-pending check.
        Index(
            "ux_property_link_requests_pending",
            "resident_id",
            "property_id",
            unique=True,
            postgresql_where="status = 'PENDING'",
        ),
        ForeignKeyConstraint(
            ["society_id", "resident_id"],
            ["users.society_id", "users.id"],
            name="fk_property_link_requests_society_resident",
        ),
        ForeignKeyConstraint(
            ["society_id", "property_id"],
            ["properties.society_id", "properties.id"],
            name="fk_property_link_requests_society_property",
        ),
    )


class SubAdminScope(Base, UUIDPKMixin):
    __tablename__ = "sub_admin_scopes"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    sub_admin_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index(
            "ux_sub_admin_scopes_active",
            "sub_admin_id",
            "location_id",
            unique=True,
            postgresql_where="revoked_at IS NULL",
        ),
        # v1.5 addition — Section 7: at most one active Sub-admin per Wing/
        # Row. The index above alone only stops the SAME person being
        # scoped to the SAME location twice; this stops two DIFFERENT
        # residents both holding active scope over the same location.
        # DB-level backstop for the service-layer check in subadmin_service
        # .promote_to_subadmin/assign_additional_scope.
        Index(
            "ux_sub_admin_scopes_location_active",
            "location_id",
            unique=True,
            postgresql_where="revoked_at IS NULL",
        ),
        ForeignKeyConstraint(
            ["society_id", "sub_admin_id"],
            ["users.society_id", "users.id"],
            name="fk_sub_admin_scopes_society_subadmin",
        ),
        ForeignKeyConstraint(
            ["society_id", "location_id"],
            ["society_locations.society_id", "society_locations.id"],
            name="fk_sub_admin_scopes_society_location",
        ),
    )
    # Sub-admin API scope check (Section 27/Section 7): every request re-derives
    # JWT.user -> role=SUB_ADMIN (not revoked) -> sub_admin_scopes (not revoked)
    # -> location_id -> properties.location_id match, else 403. See app/services/
    # scope_service.py (Step 3).


class RoleRequest(Base, UUIDPKMixin):
    __tablename__ = "role_requests"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    request_type: Mapped[RoleRequestType] = mapped_column(
        pg_enum(RoleRequestType, "role_request_type_enum"),
        nullable=False,
        default=RoleRequestType.SUB_ADMIN_RESIGNATION,
    )
    status: Mapped[RoleRequestStatus] = mapped_column(
        pg_enum(RoleRequestStatus, "role_request_status_enum"),
        nullable=False,
        default=RoleRequestStatus.PENDING,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["society_id", "user_id"],
            ["users.society_id", "users.id"],
            name="fk_role_requests_society_user",
        ),
    )
