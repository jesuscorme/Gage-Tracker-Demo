import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import request_id_var
from app.modules.audit.models import AuditEvent


def plain(value: Any) -> Any:
    """JSON-friendly, comparison-stable representation (Decimal 10.000 == 10)."""
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list]:
    """Return ``{field: [old, new]}`` for every field whose value changed."""
    return {
        k: [plain(before.get(k)), plain(after.get(k))]
        for k in after
        if plain(before.get(k)) != plain(after.get(k))
    }


def snapshot(entity: Any, fields: list[str]) -> dict[str, Any]:
    return {f: plain(getattr(entity, f)) for f in fields}


def record(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: Any = None,
    organization_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    changes: dict | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
) -> AuditEvent:
    """Add an audit event to the current transaction.

    The event is committed together with the business change, so a rolled-back change
    never leaves an orphan audit record and a committed change always has one.
    """
    event = AuditEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        changes={k: plain(v) if not isinstance(v, (list, dict)) else v for k, v in (changes or {}).items()}
        or None,
        reason=reason,
        request_id=request_id_var.get(),
        ip_address=ip_address,
    )
    db.add(event)
    return event
