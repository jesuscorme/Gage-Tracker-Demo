"""Transactional outbox of domain events.

Business services call :func:`app.modules.events.service.emit` inside their own
transaction, so an event exists if and only if the business change was committed.
Webhook delivery (app/modules/integrations) reads from this table.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

EVENT_TYPES = (
    "gage.created",
    "gage.overdue",
    "calibration.released",
    "certificate.uploaded",
    "lab.request_created",
    "lab.work_order_completed",
    "msa.study_completed",
    "oot.case_created",
)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        # Protection against duplicates: one event per business fact.
        UniqueConstraint("organization_id", "dedupe_key"),
        Index("ix_outbox_events_org_created", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    event_type: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID]
    dedupe_key: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
