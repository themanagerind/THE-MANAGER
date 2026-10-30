"""
Manager & Operations — Schema Spec v1.3, Section 2.4.

Tables: task_suggestions (platform-global), manager_todos, complaints,
complaint_assignments, visitors, visitor_logs, notices, amenities,
amenity_bookings.
"""
import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import BookingStatus, ComplaintStatus, TodoStatus, VisitorStatus
from app.models.mixins import CreatedAtOnlyMixin, TimestampMixin, UUIDPKMixin
from app.models.pg_enum import pg_enum


class TaskSuggestion(Base, UUIDPKMixin, CreatedAtOnlyMixin):
    """Platform-global — no society_id (Section 16). Add-only: no is_active,
    no category, no edit mechanism (v1.1 fix)."""

    __tablename__ = "task_suggestions"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )


class ManagerDailyTask(Base, UUIDPKMixin, TimestampMixin):
    """A Manager's recurring daily-duty checklist (v1.4 addition) — the
    Admin ticks which task_suggestions apply to a given Manager once
    (typically at staff-creation time), instead of calling ManagerTodo's
    one-off assign_todo every single day for the same recurring task.
    is_active lets the Admin turn a task off later without losing history
    (unique on manager_id+task_suggestion_id — toggle the existing row
    rather than duplicate it). manager_todo_service generates today's
    actual ManagerTodo row from each active one lazily, on the Manager's
    own todo-list read (same compute-on-read, no cron approach as the
    rest of this schema — see 0011's penalty comment)."""

    __tablename__ = "manager_daily_tasks"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    task_suggestion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task_suggestions.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["society_id", "manager_id"],
            ["users.society_id", "users.id"],
            name="fk_manager_daily_tasks_society_manager",
        ),
        UniqueConstraint(
            "manager_id", "task_suggestion_id", name="ux_manager_daily_tasks_manager_task"
        ),
    )


class ManagerTodo(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "manager_todos"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    task_suggestion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task_suggestions.id"), nullable=False
    )
    task_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[TodoStatus] = mapped_column(
        pg_enum(TodoStatus, "todo_status_enum"), nullable=False, default=TodoStatus.PENDING
    )
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["society_id", "manager_id"],
            ["users.society_id", "users.id"],
            name="fk_manager_todos_society_manager",
        ),
    )


class Complaint(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "complaints"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ComplaintStatus] = mapped_column(
        pg_enum(ComplaintStatus, "complaint_status_enum"),
        nullable=False,
        default=ComplaintStatus.OPEN,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["society_id", "property_id"],
            ["properties.society_id", "properties.id"],
            name="fk_complaints_society_property",
        ),
        ForeignKeyConstraint(
            ["society_id", "resident_id"],
            ["users.society_id", "users.id"],
            name="fk_complaints_society_resident",
        ),
    )


class ComplaintAssignment(Base, UUIDPKMixin):
    """Append-only (Section 17): every (re)assignment is a new row."""

    __tablename__ = "complaint_assignments"

    complaint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("complaints.id"), nullable=False
    )
    # must hold MANAGER role — service-level check (Section 49.8)
    assigned_to: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # at most one unresolved/current assignment per complaint (audit item J)
        Index(
            "ux_complaint_assignments_current",
            "complaint_id",
            unique=True,
            postgresql_where="completed_at IS NULL",
        ),
    )


class ComplaintRating(Base, UUIDPKMixin, CreatedAtOnlyMixin):
    """One-time rating of the Manager who resolved a complaint (Reports
    feature, v1.5) — feeds the Manager Performance report Admin/Sub-
    admin/Resident see, and (per the Admin's stated intent) is meant to
    inform Manager promotion decisions down the line. Immutable once
    given (append-only, same as ManagerTodo's completed_at) — no edit
    endpoint exists, and manager_id is captured at rating time from the
    complaint's current assignment rather than looked up live, so a
    later reassignment can't retroactively change who a past rating
    counts for.

    rated_by is NOT always the complaint's own resident_id (v1.6
    extension): a Resident may only rate a complaint they themselves
    raised, but a Sub-admin may rate ANY complaint within their
    assigned Wing/Row scope regardless of who raised it — or one they
    raised themselves even if it's outside that scope, since Sub-admin
    is a promoted Resident and keeps that dual identity (Section 6).
    See complaint_service.rate_complaint for the authorization rule."""

    __tablename__ = "complaint_ratings"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("complaints.id"), nullable=False, unique=True
    )
    rated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rating: Mapped[int] = mapped_column(nullable=False)

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_complaint_ratings_rating_range"),
        ForeignKeyConstraint(
            ["society_id", "rated_by"], ["users.society_id", "users.id"],
            name="fk_complaint_ratings_society_rated_by",
        ),
        ForeignKeyConstraint(
            ["society_id", "manager_id"], ["users.society_id", "users.id"],
            name="fk_complaint_ratings_society_manager",
        ),
    )


class Visitor(Base, UUIDPKMixin, CreatedAtOnlyMixin):
    __tablename__ = "visitors"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    visitor_name: Mapped[str] = mapped_column(String(150), nullable=False)
    visitor_mobile: Mapped[str | None] = mapped_column(String(15), nullable=True)
    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[VisitorStatus] = mapped_column(
        pg_enum(VisitorStatus, "visitor_status_enum"),
        nullable=False,
        default=VisitorStatus.PRE_APPROVED,
    )
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["society_id", "property_id"],
            ["properties.society_id", "properties.id"],
            name="fk_visitors_society_property",
        ),
        ForeignKeyConstraint(
            ["society_id", "resident_id"],
            ["users.society_id", "users.id"],
            name="fk_visitors_society_resident",
        ),
        # Allowed transitions (Section 49.13, service-level):
        # PRE_APPROVED -> EXPECTED -> ENTERED -> EXITED
        # PRE_APPROVED -> CANCELLED ; EXPECTED -> CANCELLED
        # PRE_APPROVED -> ENTERED (skip allowed)
    )


class VisitorLog(Base, UUIDPKMixin, CreatedAtOnlyMixin):
    """API projection rule: Guard-facing endpoints on this table must project
    only visitor_name/visitor_mobile/property.house_number/status — never join
    into payments, wallets, or resident profile fields (Section 21)."""

    __tablename__ = "visitor_logs"

    visitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visitors.id"), nullable=False
    )
    guard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    entry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    exit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Notice(Base, UUIDPKMixin, TimestampMixin):
    """No is_active (v1.1 fix), no wing/row targeting (Section 49.7) —
    society-wide only."""

    __tablename__ = "notices"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )


class Amenity(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "amenities"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    __table_args__ = (
        # v1.3 addition — supports composite FK from amenity_bookings
        UniqueConstraint("society_id", "id", name="ux_amenities_society_id_id"),
    )


class AmenityBooking(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "amenity_bookings"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False
    )
    amenity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        pg_enum(BookingStatus, "booking_status_enum"),
        nullable=False,
        default=BookingStatus.PENDING,
    )
    # Admin (any scope) or Sub-admin (property's scope) — Section 20
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        CheckConstraint("start_time < end_time", name="ck_amenity_bookings_time_range"),
        ForeignKeyConstraint(
            ["society_id", "amenity_id"],
            ["amenities.society_id", "amenities.id"],
            name="fk_amenity_bookings_society_amenity",
        ),
        ForeignKeyConstraint(
            ["society_id", "property_id"],
            ["properties.society_id", "properties.id"],
            name="fk_amenity_bookings_society_property",
        ),
        ForeignKeyConstraint(
            ["society_id", "resident_id"],
            ["users.society_id", "users.id"],
            name="fk_amenity_bookings_society_resident",
        ),
    )
