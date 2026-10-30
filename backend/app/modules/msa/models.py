"""MSA Management.

* :class:`MsaStudy` — the study record (method, characteristic, gage, design, workflow).
* :class:`MsaObservation` — raw data. Rows are immutable; a correction supersedes the
  original row, which is kept (database trigger).
* :class:`MsaRun` — one execution of the statistical engine: input snapshot and hash,
  method, algorithm/engine versions, criteria snapshot, results and decision.
  Append-only (database trigger): an engine upgrade never rewrites history.
* :class:`MsaCriteriaSet` — acceptance criteria, versioned, approved by a second person.
* :class:`MsaReport` — issued PDF reports, each tied to the exact run it shows.
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

METHODS = ("GRR_CROSSED_AR", "GRR_CROSSED_ANOVA", "GRR_NESTED_ANOVA", "ATTRIBUTE_AGREEMENT", "BIAS", "LINEARITY",
           "STABILITY", "TYPE1")
SOURCES = ("MANUAL", "IMPORT", "DEVICE")
DECISIONS = ("ACCEPTABLE", "CONDITIONAL", "NOT_ACCEPTABLE", "INCONCLUSIVE", "NO_CRITERIA")
CRITERIA_SCOPES = ("ORGANIZATION", "PLANT", "CUSTOMER")
CRITERIA_STATUSES = ("DRAFT", "APPROVED", "RETIRED")


class MsaStudy(TimestampMixin, Base):
    __tablename__ = "msa_studies"
    __table_args__ = (
        UniqueConstraint("organization_id", "study_code"),
        CheckConstraint(f"method IN {METHODS}", name="method_valid"),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="dates_ordered"),
        Index("ix_msa_studies_gage", "gage_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    plant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plants.id", ondelete="RESTRICT"))
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    study_code: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    method: Mapped[str] = mapped_column(String(30))
    characteristic: Mapped[str] = mapped_column(String(200))
    part_number: Mapped[str | None] = mapped_column(String(80))
    part_revision: Mapped[str | None] = mapped_column(String(20))
    customer: Mapped[str | None] = mapped_column(String(200))
    gage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gages.id", ondelete="RESTRICT"))
    responsible_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40))
    workflow_version: Mapped[int] = mapped_column(Integer, default=0)
    design: Mapped[dict[str, Any]] = mapped_column(JSONB)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    criteria_set_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("msa_criteria_sets.id", ondelete="RESTRICT"))
    notes: Mapped[str | None] = mapped_column(Text)
    # Human conclusion recorded during review (may differ from the computed decision only with justification).
    final_decision: Mapped[str | None] = mapped_column(String(20))
    final_comment: Mapped[str | None] = mapped_column(String(2000))
    concluded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))

    gage: Mapped[Gage] = relationship(lazy="joined")


class MsaObservation(Base):
    __tablename__ = "msa_observations"
    __table_args__ = (
        CheckConstraint(f"source IN {SOURCES}", name="source_valid"),
        Index("ix_msa_observations_study", "study_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("msa_studies.id", ondelete="RESTRICT"))
    operator: Mapped[str | None] = mapped_column(String(60))
    part: Mapped[str | None] = mapped_column(String(60))
    trial: Mapped[int | None] = mapped_column(Integer)
    subgroup: Mapped[int | None] = mapped_column(Integer)
    value: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    category: Mapped[str | None] = mapped_column(String(60))
    reference: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    measured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(10))
    import_job_id: Mapped[uuid.UUID | None] = mapped_column()
    device_reading_id: Mapped[uuid.UUID | None] = mapped_column()
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("msa_observations.id", ondelete="RESTRICT"))
    superseded: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    correction_reason: Mapped[str | None] = mapped_column(String(500))
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())


class MsaCriteriaSet(Base):
    __tablename__ = "msa_criteria_sets"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", "version"),
        CheckConstraint(f"method IN {METHODS}", name="method_valid"),
        CheckConstraint(f"scope IN {CRITERIA_SCOPES}", name="scope_valid"),
        CheckConstraint(f"status IN {CRITERIA_STATUSES}", name="status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(30))
    scope: Mapped[str] = mapped_column(String(15))
    plant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plants.id", ondelete="RESTRICT"))
    customer: Mapped[str | None] = mapped_column(String(200))
    rules: Mapped[list[dict]] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(10), default="DRAFT")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_reason: Mapped[str | None] = mapped_column(String(500))


class MsaRun(Base):
    __tablename__ = "msa_runs"
    __table_args__ = (
        UniqueConstraint("study_id", "run_number"),
        CheckConstraint(f"decision IN {DECISIONS}", name="decision_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("msa_studies.id", ondelete="RESTRICT"), index=True)
    run_number: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(30))
    algorithm_version: Mapped[str] = mapped_column(String(20))
    engine_version: Mapped[str] = mapped_column(String(20))
    validation_status: Mapped[str] = mapped_column(String(20))
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    input_hash: Mapped[str] = mapped_column(String(64))
    results: Mapped[dict[str, Any]] = mapped_column(JSONB)
    criteria_set_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("msa_criteria_sets.id", ondelete="RESTRICT"))
    criteria_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    evaluation: Mapped[list[dict] | None] = mapped_column(JSONB)
    decision: Mapped[str] = mapped_column(String(20))
    gage_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    calculated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())


class MsaReport(Base):
    __tablename__ = "msa_reports"
    __table_args__ = (UniqueConstraint("study_id", "revision"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("msa_studies.id", ondelete="RESTRICT"), index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("msa_runs.id", ondelete="RESTRICT"))
    revision: Mapped[int] = mapped_column(Integer)
    attachment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attachments.id", ondelete="RESTRICT"))
    issued_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
