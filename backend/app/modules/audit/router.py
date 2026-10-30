import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.identity.deps import TenantContext, require
from app.modules.identity.models import User
from app.modules.identity.permissions import P

router = APIRouter(prefix="/audit-events", tags=["audit"])


class AuditEventOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    action: str
    entity_type: str
    entity_id: str | None
    actor_user_id: uuid.UUID | None
    actor_name: str | None
    changes: dict | None
    reason: str | None
    request_id: str | None


class AuditPage(BaseModel):
    items: list[AuditEventOut]
    total: int


def query_events(
    db: Session,
    organization_id: uuid.UUID,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AuditPage:
    stmt = select(AuditEvent, User.full_name).outerjoin(User, User.id == AuditEvent.actor_user_id).where(
        AuditEvent.organization_id == organization_id
    )
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditEvent.entity_id == entity_id)
    if action:
        stmt = stmt.where(AuditEvent.action.startswith(action))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(AuditEvent.created_at.desc(), AuditEvent.id).limit(limit).offset(offset))
    return AuditPage(
        total=total,
        items=[
            AuditEventOut(
                id=e.id, created_at=e.created_at, action=e.action, entity_type=e.entity_type,
                entity_id=e.entity_id, actor_user_id=e.actor_user_id, actor_name=name,
                changes=e.changes, reason=e.reason, request_id=e.request_id,
            )
            for e, name in rows
        ],
    )


@router.get("", response_model=AuditPage)
def list_audit_events(
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: TenantContext = Depends(require(P.AUDIT_READ)),
):
    return query_events(
        ctx.db, ctx.organization_id, entity_type=entity_type, entity_id=entity_id,
        action=action, limit=limit, offset=offset,
    )
