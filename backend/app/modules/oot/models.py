"""OOT & Impact Analysis.

An :class:`OotCase` records a gage found out of tolerance (normally from a released
calibration whose As Found was out of tolerance), the restriction applied to the gage,
the retrospective analysis (:class:`OotImpactItem` — records the system identified in
the potentially affected period, plus manual entries for information the system does
not hold) and the containment/corrective actions (:class:`OotAction`).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text,
                        UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.modules.gages.models import Gage

RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")
ITEM_TYPES = ("INSPECTION_RESULT", "WORK_ORDER", "GAGE_MOVEMENT", "MSA_STUDY", "DEVICE_READINGS", "MANUAL")
ASSESSMENTS = ("PENDING", "NO_IMPACT", "IMPACT", "REINSPECT")
ACTION_TYPES = ("CONTAINMENT", "REINSPECTION", "CORRECTIVE", "CUSTOMER_NOTIFICATION", "OTHER")
ACTION_STATUSES = ("OPEN", "DONE", "CANCELLED")
CLOSE_REQUIREMENTS = ("risk_assessment", "disposition", "corrective_actions", "impact_items_assessed",
                      "actions_completed", "customer_notification_decided", "evidence_attached",
                      "gage_released_or_retired")


class OotSettings(Base):
    __tablename__ = "oot_settings"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"),
                                                       primary_key=True)
    restrict_on_detection: Mapped[bool] = mapped_column(Boolean)
    auto_create_from_calibration: Mapped[bool] = mapped_column(Boolean)
    close_requirements: Mapped[list[str]] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OotCase(TimestampMixin, Base):
    __tablename__ = "oot_cases"
    __table_args__ = (
        UniqueConstraint("organization_id", "case_code"),
        CheckConstraint(f"risk_level IS NULL OR risk_level IN {RISK_LEVELS}", name="risk_valid"),
        Index("ix_oot_cases_gage", "gage_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    plant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plants.id", ondelete="RESTRICT"))
    case_code: Mapped[str] = mapped_column(String(30))
    gage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gages.id", ondelete="RESTRICT"))
    calibration_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calibration_activities.id",
                                                                        ondelete="RESTRICT"), unique=True)
    detection_source: Mapped[str] = mapped_column(String(15))         # CALIBRATION | MANUAL
    detected_on: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text)
    found_result: Mapped[str | None] = mapped_column(String(500))
    tolerance: Mapped[str | None] = mapped_column(String(200))
    max_deviation: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    as_found: Mapped[list[dict] | None] = mapped_column(JSONB)
    as_left: Mapped[list[dict] | None] = mapped_column(JSONB)
    responsible_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(40))
    workflow_version: Mapped[int] = mapped_column(Integer, default=0)
    # Restriction of the gage.
    restriction_applied: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    gage_prior_control_status: Mapped[str | None] = mapped_column(String(20))
    gage_released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gage_released_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    gage_release_reason: Mapped[str | None] = mapped_column(String(1000))
    # Retrospective analysis.
    last_acceptable_calibration_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("calibration_activities.id", ondelete="RESTRICT"))
    impact_start: Mapped[date | None] = mapped_column(Date)
    impact_end: Mapped[date | None] = mapped_column(Date)
    analysis_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    limitations: Mapped[str | None] = mapped_column(Text)
    # Investigation record.
    risk_level: Mapped[str | None] = mapped_column(String(10))
    risk_assessment: Mapped[str | None] = mapped_column(Text)
    investigation_scope: Mapped[str | None] = mapped_column(Text)
    reinspection: Mapped[str | None] = mapped_column(Text)
    containment: Mapped[str | None] = mapped_column(Text)
    disposition: Mapped[str | None] = mapped_column(Text)
    corrective_actions: Mapped[str | None] = mapped_column(Text)
    customer_notification_required: Mapped[bool | None] = mapped_column(Boolean)
    customer_notification: Mapped[str | None] = mapped_column(Text)
    customer_notified_on: Mapped[date | None] = mapped_column(Date)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))

    gage: Mapped[Gage] = relationship(lazy="joined")


class OotImpactItem(Base):
    __tablename__ = "oot_impact_items"
    __table_args__ = (
        CheckConstraint(f"item_type IN {ITEM_TYPES}", name="item_type_valid"),
        CheckConstraint(f"assessment IN {ASSESSMENTS}", name="assessment_valid"),
        Index("uq_oot_impact_items_ref", "case_id", "item_type", "ref_id", unique=True,
              postgresql_where=text("ref_id IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("oot_cases.id", ondelete="RESTRICT"), index=True)
    item_type: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(10))                 # SYSTEM | MANUAL
    ref_id: Mapped[uuid.UUID | None] = mapped_column()
    ref_code: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(1000))
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    assessment: Mapped[str] = mapped_column(String(12), default="PENDING")
    assessment_note: Mapped[str | None] = mapped_column(String(2000))
    assessed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())


class OotAction(Base):
    __tablename__ = "oot_actions"
    __table_args__ = (
        CheckConstraint(f"action_type IN {ACTION_TYPES}", name="action_type_valid"),
        CheckConstraint(f"status IN {ACTION_STATUSES}", name="status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("oot_cases.id", ondelete="RESTRICT"), index=True)
    action_type: Mapped[str] = mapped_column(String(25))
    description: Mapped[str] = mapped_column(String(2000))
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="OPEN")
    result_note: Mapped[str | None] = mapped_column(String(2000))
    completed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
