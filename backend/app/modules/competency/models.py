import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin

PROFILE_TYPES = (
    "METROLOGY_TECHNICIAN", "LAB_TECHNICIAN", "INTERNAL_CALIBRATOR", "VERIFIER",
    "MSA_EVALUATOR", "TECHNICAL_REVIEWER", "APPROVER",
)
RECORD_TYPES = ("TRAINING", "EVALUATION", "CERTIFICATION")
RECORD_RESULTS = ("PASSED", "FAILED", "NOT_APPLICABLE")

# Activities that require a personal, current authorization.
ACTIVITIES = (
    "INTERNAL_CALIBRATION",     # execute internal calibrations
    "ROUTINE_VERIFICATION",     # execute routine verifications
    "TECHNICAL_REVIEW",         # technical review of calibration activities / measurement reports
    "APPROVAL",                 # approve calibration activities
    "LAB_SERVICE",              # execute laboratory work orders
    "DIMENSIONAL_INSPECTION",   # capture dimensional inspection results
    "MSA_EVALUATION",           # reserved for MSA Management (phase 6)
)


class PersonnelProfile(TimestampMixin, Base):
    __tablename__ = "personnel_profiles"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    employee_number: Mapped[str | None] = mapped_column(String(40))
    job_title: Mapped[str | None] = mapped_column(String(120))
    plant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plants.id", ondelete="RESTRICT"))
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    profile_types: Mapped[list[str]] = mapped_column(ARRAY(String(30)), default=list, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    notes: Mapped[str | None] = mapped_column(Text)


class Competency(TimestampMixin, Base):
    """Organization catalogue of competencies (e.g. 'Caliper calibration per PR-MET-04')."""

    __tablename__ = "competencies"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(1000))
    # Default validity of a record (months); null = does not expire.
    validity_months: Mapped[int | None]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class CompetencyRecord(Base):
    """Training, evaluation or certification of a person. Append-only."""

    __tablename__ = "competency_records"
    __table_args__ = (
        CheckConstraint(f"record_type IN {RECORD_TYPES}", name="record_type_valid"),
        CheckConstraint(f"result IN {RECORD_RESULTS}", name="result_valid"),
        CheckConstraint("valid_until IS NULL OR valid_until >= completed_on", name="validity_after_completion"),
        Index("ix_competency_records_user", "organization_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    competency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("competencies.id", ondelete="RESTRICT"))
    record_type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str | None] = mapped_column(String(200))
    completed_on: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    result: Mapped[str] = mapped_column(String(20))
    score: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())


class Authorization(Base):
    """Personal authorization to perform an activity, optionally limited to a gage type and/or plant.

    Never edited: revoked (with reason) and granted again if conditions change.
    """

    __tablename__ = "authorizations"
    __table_args__ = (
        CheckConstraint(f"activity IN {ACTIVITIES}", name="activity_valid"),
        CheckConstraint("valid_until IS NULL OR valid_until >= valid_from", name="validity_order"),
        Index("ix_authorizations_lookup", "organization_id", "user_id", "activity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    activity: Mapped[str] = mapped_column(String(30))
    gage_type_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("gage_types.id", ondelete="RESTRICT"))
    plant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plants.id", ondelete="RESTRICT"))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    basis: Mapped[str | None] = mapped_column(String(500))
    competency_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("competency_records.id", ondelete="RESTRICT"))
    granted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    revoke_reason: Mapped[str | None] = mapped_column(String(500))
