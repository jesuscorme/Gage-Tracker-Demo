import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.modules.gages.models import Gage

ACTIVITY_TYPES = ("EXTERNAL_CALIBRATION", "INTERNAL_CALIBRATION", "ROUTINE_VERIFICATION")
STATUSES = (
    "PLANNED", "REQUESTED", "SCHEDULED", "IN_PROGRESS", "PENDING_REVIEW", "PENDING_APPROVAL",
    "APPROVED", "RELEASED", "CANCELLED",
)
RESULTS = ("PASS", "PASS_AFTER_ADJUSTMENT", "FAIL")


class CalibrationSetting(Base):
    """Which activity types are enabled and which evidence each requires.

    ``plant_id`` NULL is the organization default; a plant row overrides it.
    """

    __tablename__ = "calibration_settings"
    __table_args__ = (
        UniqueConstraint("organization_id", "plant_id", "activity_type", postgresql_nulls_not_distinct=True),
        CheckConstraint(f"activity_type IN {ACTIVITY_TYPES}", name="activity_type_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    plant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plants.id", ondelete="RESTRICT"))
    activity_type: Mapped[str] = mapped_column(String(30))
    enabled: Mapped[bool] = mapped_column(Boolean)
    require_certificate: Mapped[bool] = mapped_column(Boolean)
    require_standard: Mapped[bool] = mapped_column(Boolean)
    require_as_found: Mapped[bool] = mapped_column(Boolean)
    require_environment: Mapped[bool] = mapped_column(Boolean)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CalibrationActivity(TimestampMixin, Base):
    __tablename__ = "calibration_activities"
    __table_args__ = (
        UniqueConstraint("organization_id", "calibration_code"),
        CheckConstraint(f"activity_type IN {ACTIVITY_TYPES}", name="activity_type_valid"),
        CheckConstraint(f"status IN {STATUSES}", name="status_valid"),
        CheckConstraint(f"result IS NULL OR result IN {RESULTS}", name="result_valid"),
        Index("ix_calibration_activities_gage", "organization_id", "gage_id"),
        Index("ix_calibration_activities_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    plant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plants.id", ondelete="RESTRICT"))
    gage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gages.id", ondelete="RESTRICT"))
    calibration_code: Mapped[str] = mapped_column(String(30))
    activity_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="PLANNED")

    # Planning
    planned_date: Mapped[date] = mapped_column(Date)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    provider_name: Mapped[str | None] = mapped_column(String(200))
    provider_accreditation: Mapped[str | None] = mapped_column(String(120))
    # Internal: technician who performs it. External: responsible who coordinates with the lab.
    technician_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))

    # Execution
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    performed_date: Mapped[date | None] = mapped_column(Date)
    method: Mapped[str | None] = mapped_column(String(300))
    environment_temperature: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    environment_humidity: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    environment_notes: Mapped[str | None] = mapped_column(String(300))
    uncertainty: Mapped[str | None] = mapped_column(String(200))
    adjusted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    # Manual overall result, used only when no measurement points are recorded.
    declared_result: Mapped[str | None] = mapped_column(String(30))
    observations: Mapped[str | None] = mapped_column(Text)

    # Outcome (fixed at submission)
    result: Mapped[str | None] = mapped_column(String(30))
    as_found_in_tolerance: Mapped[bool | None] = mapped_column(Boolean)
    as_left_in_tolerance: Mapped[bool | None] = mapped_column(Boolean)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))

    # Review / approval / release
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_comments: Mapped[str | None] = mapped_column(String(2000))
    approver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[date | None] = mapped_column(Date)

    cancel_reason: Mapped[str | None] = mapped_column(String(1000))
    # Gage controlled status before this activity put it In Calibration (restored on cancel).
    gage_prior_control_status: Mapped[str | None] = mapped_column(String(20))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))

    gage: Mapped[Gage] = relationship(lazy="joined")


class CalibrationPoint(Base):
    """One measured point, As Found or As Left. Append-only: a correction is a new row
    that supersedes the previous one, which is kept."""

    __tablename__ = "calibration_points"
    __table_args__ = (
        CheckConstraint("phase IN ('AS_FOUND','AS_LEFT')", name="phase_valid"),
        CheckConstraint("lower_limit <= upper_limit", name="limits_ordered"),
        Index("ix_calibration_points_activity", "calibration_id", "phase"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    calibration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calibration_activities.id", ondelete="RESTRICT"))
    phase: Mapped[str] = mapped_column(String(10))
    sequence: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(String(200))
    nominal: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    lower_limit: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    upper_limit: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    measured: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    unit: Mapped[str | None] = mapped_column(String(20))
    uncertainty: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    in_tolerance: Mapped[bool] = mapped_column(Boolean)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calibration_points.id", ondelete="RESTRICT"))
    superseded: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    correction_reason: Mapped[str | None] = mapped_column(String(500))
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())


class CalibrationCertificate(Base):
    """Certificate of a calibration activity. Never replaced in place: a new one supersedes."""

    __tablename__ = "calibration_certificates"
    __table_args__ = (CheckConstraint("status IN ('CURRENT','SUPERSEDED')", name="status_valid"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    calibration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calibration_activities.id", ondelete="RESTRICT"),
                                                      index=True)
    gage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gages.id", ondelete="RESTRICT"), index=True)
    certificate_number: Mapped[str] = mapped_column(String(80))
    issuer: Mapped[str] = mapped_column(String(200))
    issue_date: Mapped[date] = mapped_column(Date)
    attachment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attachments.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), default="CURRENT")
    superseded_reason: Mapped[str | None] = mapped_column(String(500))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())


class CalibrationStandardUsage(Base):
    """Standard used in an activity, with a snapshot of its condition on that date."""

    __tablename__ = "calibration_standard_usages"
    __table_args__ = (UniqueConstraint("calibration_id", "standard_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    calibration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calibration_activities.id", ondelete="RESTRICT"))
    standard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("standards.id", ondelete="RESTRICT"), index=True)
    used_on: Mapped[date] = mapped_column(Date)
    standard_status: Mapped[str] = mapped_column(String(20))
    certificate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("standard_certificates.id", ondelete="RESTRICT"))
    valid_until: Mapped[date | None] = mapped_column(Date)
    is_exception: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    exception_reason: Mapped[str | None] = mapped_column(String(500))
    exception_authorized_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())


class CalibrationStatusHistory(Base):
    __tablename__ = "calibration_status_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    calibration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calibration_activities.id", ondelete="RESTRICT"),
                                                      index=True)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(String(2000))
    data: Mapped[dict | None] = mapped_column(JSONB)
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
