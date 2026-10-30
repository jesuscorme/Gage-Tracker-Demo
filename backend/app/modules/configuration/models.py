"""Versioned platform configuration.

Every configurable object (custom field, form, workflow, approval matrix, business rule)
is a :class:`ConfigItem` whose content lives in immutable :class:`ConfigVersion` rows.
A change is a new version; previous versions stay queryable. Kinds that need approval
start as DRAFT and become ACTIVE only when another user approves them.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin

KINDS = ("CUSTOM_FIELD", "FORM", "WORKFLOW", "APPROVAL_MATRIX", "BUSINESS_RULE")
VERSION_STATUSES = ("DRAFT", "ACTIVE", "SUPERSEDED", "REJECTED")


class ConfigItem(TimestampMixin, Base):
    __tablename__ = "config_items"
    __table_args__ = (
        UniqueConstraint("organization_id", "kind", "key"),
        CheckConstraint(f"kind IN {KINDS}", name="kind_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    key: Mapped[str] = mapped_column(String(120))
    entity_type: Mapped[str] = mapped_column(String(40))
    active_version: Mapped[int | None] = mapped_column(Integer)
    is_retired: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class ConfigVersion(Base):
    """Immutable content; only the status/approval columns may change (database trigger)."""

    __tablename__ = "config_versions"
    __table_args__ = (
        UniqueConstraint("item_id", "version"),
        CheckConstraint(f"status IN {VERSION_STATUSES}", name="status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("config_items.id", ondelete="RESTRICT"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    change_summary: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(12))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_comment: Mapped[str | None] = mapped_column(String(1000))


class CustomFieldValue(Base):
    __tablename__ = "custom_field_values"
    __table_args__ = (UniqueConstraint("organization_id", "entity_type", "entity_id", "field_key"),
                      Index("ix_custom_field_values_entity", "entity_type", "entity_id"))

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID]
    field_key: Mapped[str] = mapped_column(String(60))
    value: Mapped[Any] = mapped_column(JSONB)
    field_version: Mapped[int] = mapped_column(Integer)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp(),
                                                 onupdate=func.clock_timestamp())


class WorkflowEvent(Base):
    """Append-only history of workflow transitions, approval votes and escalations."""

    __tablename__ = "workflow_events"
    __table_args__ = (Index("ix_workflow_events_entity", "entity_type", "entity_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID]
    event_type: Mapped[str] = mapped_column(String(20))     # TRANSITION | VOTE | ESCALATION | CREATED
    workflow_version: Mapped[int] = mapped_column(Integer)
    transition: Mapped[str | None] = mapped_column(String(40))
    action: Mapped[str | None] = mapped_column(String(20))
    from_state: Mapped[str | None] = mapped_column(String(40))
    to_state: Mapped[str | None] = mapped_column(String(40))
    comment: Mapped[str | None] = mapped_column(String(2000))
    data: Mapped[dict | None] = mapped_column(JSONB)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
