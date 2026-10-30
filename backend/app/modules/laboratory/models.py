import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin

PRIORITIES = ("LOW", "NORMAL", "HIGH", "URGENT")
REQUEST_STATUSES = ("SUBMITTED", "APPROVED", "REJECTED", "IN_PROGRESS", "COMPLETED", "CANCELLED")
WO_STATUSES = ("PENDING", "SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED")


class LabSettings(Base):
    __tablename__ = "lab_settings"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"),
                                                       primary_key=True)
    # Productive hours per technician per working day (capacity basis).
    hours_per_technician_day: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("8"))
    # ISO weekdays considered working days (1 = Monday).
    working_days: Mapped[list[int]] = mapped_column(JSONB, default=lambda: [1, 2, 3, 4, 5])


class LabService(TimestampMixin, Base):
    __tablename__ = "lab_services"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(1000))
    standard_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    # Authorization activity the assigned technician must hold.
    required_activity: Mapped[str] = mapped_column(String(30), default="LAB_SERVICE")
    requires_inspection: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class TechnicianAbsence(Base):
    __tablename__ = "technician_absences"
    __table_args__ = (CheckConstraint("end_date >= start_date", name="dates_ordered"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ServiceRequest(TimestampMixin, Base):
    __tablename__ = "service_requests"
    __table_args__ = (
        UniqueConstraint("organization_id", "request_code"),
        CheckConstraint(f"priority IN {PRIORITIES}", name="priority_valid"),
        CheckConstraint(f"status IN {REQUEST_STATUSES}", name="status_valid"),
        CheckConstraint("customer_type IN ('INTERNAL','EXTERNAL')", name="customer_type_valid"),
        Index("ix_service_requests_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    plant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plants.id", ondelete="RESTRICT"))
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    request_code: Mapped[str] = mapped_column(String(30))
    requester_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    customer_type: Mapped[str] = mapped_column(String(10), default="INTERNAL")
    customer_name: Mapped[str | None] = mapped_column(String(200))
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_services.id", ondelete="RESTRICT"))
    part_number: Mapped[str | None] = mapped_column(String(80))
    part_revision: Mapped[str | None] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str] = mapped_column(String(2000))
    priority: Mapped[str] = mapped_column(String(10), default="NORMAL")
    requested_date: Mapped[date] = mapped_column(Date)
    committed_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="SUBMITTED")
    decision_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_comment: Mapped[str | None] = mapped_column(String(1000))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    service: Mapped[LabService] = relationship(lazy="joined")


work_order_equipment = Table(
    "work_order_equipment",
    Base.metadata,
    Column("work_order_id", ForeignKey("work_orders.id", ondelete="CASCADE"), primary_key=True),
    Column("gage_id", ForeignKey("gages.id", ondelete="RESTRICT"), primary_key=True),
)


class WorkOrder(TimestampMixin, Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "work_order_code"),
        CheckConstraint(f"status IN {WO_STATUSES}", name="status_valid"),
        CheckConstraint("scheduled_end IS NULL OR scheduled_end > scheduled_start", name="schedule_ordered"),
        Index("ix_work_orders_tech", "organization_id", "technician_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    plant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plants.id", ondelete="RESTRICT"))
    work_order_code: Mapped[str] = mapped_column(String(30))
    service_request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_requests.id", ondelete="RESTRICT"),
                                                          index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_services.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    priority: Mapped[str] = mapped_column(String(10))
    planned_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    technician_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[date | None] = mapped_column(Date)
    observations: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))

    request: Mapped[ServiceRequest] = relationship(lazy="joined")
    service: Mapped[LabService] = relationship(lazy="joined")


class WorkOrderEvent(Base):
    """Status / schedule history of a work order (append-only)."""

    __tablename__ = "work_order_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    work_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("work_orders.id", ondelete="RESTRICT"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(String(1000))
    data: Mapped[dict | None] = mapped_column(JSONB)
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())


class InspectionResult(Base):
    """One measured characteristic. Append-only; corrections supersede."""

    __tablename__ = "inspection_results"
    __table_args__ = (
        CheckConstraint("lower_limit <= upper_limit", name="limits_ordered"),
        CheckConstraint("result IN ('OK','NOK')", name="result_valid"),
        Index("ix_inspection_results_wo", "work_order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    work_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("work_orders.id", ondelete="RESTRICT"))
    part_number: Mapped[str] = mapped_column(String(80))
    drawing_revision: Mapped[str | None] = mapped_column(String(20))
    sample_id: Mapped[str | None] = mapped_column(String(40))
    characteristic_number: Mapped[str] = mapped_column(String(20))
    characteristic: Mapped[str] = mapped_column(String(200))
    nominal: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    lower_limit: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    upper_limit: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    measured: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    unit: Mapped[str] = mapped_column(String(20))
    gage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gages.id", ondelete="RESTRICT"))
    # Gage status at measurement time (for traceability if it later turns out OOT).
    gage_status: Mapped[str] = mapped_column(String(20))
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
    result: Mapped[str] = mapped_column(String(3))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("inspection_results.id", ondelete="RESTRICT"))
    superseded: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    correction_reason: Mapped[str | None] = mapped_column(String(500))


class MeasurementReport(Base):
    """Issued measurement report: frozen snapshot + generated PDF. Re-issue = new revision."""

    __tablename__ = "measurement_reports"
    __table_args__ = (
        UniqueConstraint("organization_id", "report_code", "revision"),
        CheckConstraint("status IN ('ISSUED','SUPERSEDED')", name="status_valid"),
        CheckConstraint("acceptance IN ('ACCEPTED','REJECTED')", name="acceptance_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    work_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("work_orders.id", ondelete="RESTRICT"), index=True)
    report_code: Mapped[str] = mapped_column(String(30))
    revision: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ISSUED")
    acceptance: Mapped[str] = mapped_column(String(10))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    observations: Mapped[str | None] = mapped_column(Text)
    revision_reason: Mapped[str | None] = mapped_column(String(500))
    technician_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
    attachment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attachments.id", ondelete="RESTRICT"))
