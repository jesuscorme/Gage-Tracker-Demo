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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.modules.identity.models import User
from app.modules.organizations.models import Department, Plant


class GageType(TimestampMixin, Base):
    """Organization-level catalogue of instrument types (caliper, micrometer, ...)."""

    __tablename__ = "gage_types"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(500))
    default_frequency_days: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class Gage(TimestampMixin, Base):
    __tablename__ = "gages"
    __table_args__ = (
        # Gage ID is unique per organization (case-insensitive: stored upper-cased).
        UniqueConstraint("organization_id", "gage_code"),
        CheckConstraint(
            "control_status IN ('ACTIVE','OUT_OF_SERVICE','IN_CALIBRATION','INACTIVE')",
            name="control_status_valid",
        ),
        CheckConstraint("calibration_frequency_days > 0", name="frequency_positive"),
        CheckConstraint(
            "range_min IS NULL OR range_max IS NULL OR range_min <= range_max", name="range_ordered"
        ),
        CheckConstraint("resolution IS NULL OR resolution > 0", name="resolution_positive"),
        Index("ix_gages_org_plant", "organization_id", "plant_id"),
        Index("ix_gages_org_due", "organization_id", "next_due_date"),
        Index("ix_gages_org_serial", "organization_id", "serial_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    plant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plants.id", ondelete="RESTRICT"))
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    gage_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gage_types.id", ondelete="RESTRICT"))
    responsible_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))

    gage_code: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(300))
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str | None] = mapped_column(String(120))
    serial_number: Mapped[str | None] = mapped_column(String(120))
    range_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    range_max: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    unit: Mapped[str | None] = mapped_column(String(20))
    resolution: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    # Free text because accuracy is expressed in many forms (±0.02 mm, 0.5 % FS, class 1).
    accuracy: Mapped[str | None] = mapped_column(String(120))
    criticality: Mapped[str | None] = mapped_column(String(10))
    location: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)

    calibration_frequency_days: Mapped[int] = mapped_column(Integer)
    last_calibration_date: Mapped[date | None] = mapped_column(Date)
    # Derived (last_calibration_date + frequency); stored so it can be indexed and sorted.
    next_due_date: Mapped[date | None] = mapped_column(Date)

    # Workflow-controlled part of the status; Calibrated/Due Soon/Overdue are derived.
    control_status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))

    gage_type: Mapped[GageType] = relationship(lazy="joined")
    plant: Mapped[Plant] = relationship(lazy="joined")
    department: Mapped[Department | None] = relationship(lazy="joined")
    responsible: Mapped[User | None] = relationship(foreign_keys=[responsible_user_id], lazy="joined")


class GageStatusHistory(Base):
    """One row per change of the controlled status (append-only)."""

    __tablename__ = "gage_status_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    gage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gages.id", ondelete="RESTRICT"), index=True)
    from_control_status: Mapped[str | None] = mapped_column(String(20))
    to_control_status: Mapped[str] = mapped_column(String(20))
    # Effective status (as shown to users) before and after the change.
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(1000))
    changed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
