import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.audit.service import plain
from app.modules.events.models import EVENT_TYPES, OutboxEvent


def emit(db: Session, organization_id: uuid.UUID, event_type: str, entity_type: str, entity_id: uuid.UUID,
         data: dict, dedupe_key: str | None = None) -> bool:
    """Queue a domain event in the current transaction. Returns False for a duplicate."""
    assert event_type in EVENT_TYPES, event_type
    key = dedupe_key or f"{event_type}:{entity_id}"
    payload = {"event": event_type, "entity_type": entity_type, "entity_id": str(entity_id),
               "occurred_at": datetime.now(UTC).isoformat(),
               "data": {k: plain(v) for k, v in data.items()}}
    inserted = db.execute(insert(OutboxEvent).values(
        id=uuid.uuid4(), organization_id=organization_id, event_type=event_type, entity_type=entity_type,
        entity_id=entity_id, dedupe_key=key, payload=payload,
    ).on_conflict_do_nothing(index_elements=["organization_id", "dedupe_key"]).returning(OutboxEvent.id)).scalar()
    return inserted is not None


def list_events(db: Session, organization_id: uuid.UUID, event_type: str | None, limit: int) -> list[OutboxEvent]:
    stmt = select(OutboxEvent).where(OutboxEvent.organization_id == organization_id)
    if event_type:
        stmt = stmt.where(OutboxEvent.event_type == event_type)
    return list(db.scalars(stmt.order_by(OutboxEvent.created_at.desc()).limit(limit)))
