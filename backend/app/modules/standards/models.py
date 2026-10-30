import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.modules.identity.models import User
from app.modules.organizations.models import Plant

CATEGORIES = (
    "GAUGE_BLOCK", "REFERENCE_STANDARD", "MASTER_PART", "SETTING_MASTER",
    "REFERENCE_INSTRUMENT", "TEMPERATURE", "PRESSURE", "OTHER",
)


class Standard(TimestampMixin, Base):
    """Reference standard / master used to calibrate or verify gages."""

    __tablename__ = "standards"
    __table_args__ = (
        UniqueConstraint("organization_id", "standard_code"),
        CheckConstraint(f"category IN {CATEGORIES}", name="category_valid"),
        CheckConstraint("control_status IN ('ACTIVE','RESTRICTED','INACTIVE')", name="control_status_valid"),
        CheckConstraint("calibration_frequency_days > 0", name="frequency_positive"),
        CheckConstraint("range_min IS NULL OR range_max IS NULL OR range_min <= range_max", name="range_ordered"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    plant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plants.id", ondelete="RESTRICT"))
    standard_code: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(30))
    # Free classification for OTHER or finer grouping (e.g. "Grade 0 steel set").
    subtype: Mapped[str | None] = mapped_column(String(120))
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str | None] = mapped_column(String(120))
    serial_number: Mapped[str | None] = mapped_column(String(120))
    range_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    range_max: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    unit: Mapped[str | None] = mapped_column(String(20))
    resolution: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    accuracy: Mapped[str | None] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(200))
    custodian_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    calibration_frequency_days: Mapped[int] = mapped_column(Integer)
    # Set from the current certificate.
    last_calibration_date: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    current_certificate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("standard_certificates.id", ondelete="RESTRICT", use_alter=True,
                   name="fk_standards_current_certificate_id_standard_certificates"))
    control_status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))

    plant: Mapped[Plant] = relationship(lazy="joined")
    custodian: Mapped[User | None] = relationship(foreign_keys=[custodian_user_id], lazy="joined")


class StandardCertificate(Base):
    """Calibration certificate of a standard. Immutable: a new one supersedes the previous."""

    __tablename__ = "standard_certificates"
    __table_args__ = (
        CheckConstraint("status IN ('CURRENT','SUPERSEDED')", name="status_valid"),
        CheckConstraint("valid_until > calibration_date", name="validity_after_calibration"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    standard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("standards.id", ondelete="RESTRICT"), index=True)
    certificate_number: Mapped[str] = mapped_column(String(80))
    issuer: Mapped[str] = mapped_column(String(200))
    accreditation: Mapped[str | None] = mapped_column(String(120))
    calibration_date: Mapped[date] = mapped_column(Date)
    issue_date: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)
    uncertainty: Mapped[str | None] = mapped_column(String(200))
    traceability: Mapped[str | None] = mapped_column(String(300))
    attachment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attachments.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), default="CURRENT")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
