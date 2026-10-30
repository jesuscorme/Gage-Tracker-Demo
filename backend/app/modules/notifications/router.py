import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.errors import BusinessRuleError

from app.modules.competency.models import Authorization, CompetencyRecord
from app.modules.gages import service as gages
from app.modules.identity.deps import TenantContext, get_tenant_context
from app.modules.identity.permissions import P
from app.modules.laboratory.models import WorkOrder
from app.modules.notifications.models import KINDS, Notification, NotificationPreference
from app.modules.standards.models import Standard

router = APIRouter(tags=["notifications"])


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: str
    title: str
    body: str | None
    link: str | None
    created_at: datetime
    read_at: datetime | None


class PreferenceIn(BaseModel):
    kind: str
    enabled: bool


@router.get("/notifications")
def list_notifications(unread_only: bool = False, ctx: TenantContext = Depends(get_tenant_context)):
    base = [Notification.organization_id == ctx.organization_id, Notification.user_id == ctx.user_id]
    stmt = select(Notification).where(*base)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    items = list(ctx.db.scalars(stmt.order_by(Notification.created_at.desc()).limit(50)))
    unread = ctx.db.scalar(select(func.count()).select_from(Notification).where(*base, Notification.read_at.is_(None)))
    return {"unread": unread, "items": [NotificationOut.model_validate(n) for n in items]}


@router.post("/notifications/read")
def mark_read(ids: list[uuid.UUID] | None = None, ctx: TenantContext = Depends(get_tenant_context)):
    """Mark the given notifications (or all) as read."""
    stmt = update(Notification).where(Notification.organization_id == ctx.organization_id,
                                      Notification.user_id == ctx.user_id, Notification.read_at.is_(None))
    if ids:
        stmt = stmt.where(Notification.id.in_(ids))
    n = ctx.db.execute(stmt.values(read_at=datetime.now(UTC))).rowcount
    ctx.db.commit()
    return {"updated": n}


@router.get("/notifications/preferences")
def get_preferences(ctx: TenantContext = Depends(get_tenant_context)):
    disabled = set(ctx.db.scalars(select(NotificationPreference.kind).where(
        NotificationPreference.organization_id == ctx.organization_id, NotificationPreference.user_id == ctx.user_id,
        NotificationPreference.enabled.is_(False))))
    return [{"kind": k, "enabled": k not in disabled} for k in KINDS]


@router.put("/notifications/preferences")
def set_preference(body: PreferenceIn, ctx: TenantContext = Depends(get_tenant_context)):
    if body.kind not in KINDS:
        raise BusinessRuleError("Unknown notification kind", code="invalid_kind", details=list(KINDS))
    ctx.db.execute(insert(NotificationPreference).values(
        id=uuid.uuid4(), organization_id=ctx.organization_id, user_id=ctx.user_id, kind=body.kind, enabled=body.enabled)
        .on_conflict_do_update(index_elements=["organization_id", "user_id", "kind"], set_={"enabled": body.enabled}))
    ctx.db.commit()
    return get_preferences(ctx)


@router.get("/alerts")
def alerts(ctx: TenantContext = Depends(get_tenant_context)):
    """Live alert counters for the header, limited to what the user may see."""
    today = ctx.today()
    horizon = today + timedelta(days=ctx.organization.due_soon_days)
    out: dict = {"as_of": today.isoformat()}
    if ctx.has(P.GAGES_READ):
        counts = gages.status_counts(ctx)
        out["gages_overdue"] = counts["OVERDUE"]
        out["gages_due_soon"] = counts["DUE_SOON"]
    if ctx.has(P.STANDARDS_READ):
        scope = [Standard.organization_id == ctx.organization_id, Standard.control_status == "ACTIVE"]
        if ctx.plant_ids is not None:
            scope.append(Standard.plant_id.in_(ctx.plant_ids))
        out["standards_expired"] = ctx.db.scalar(select(func.count()).select_from(Standard).where(
            *scope, or_(Standard.valid_until.is_(None), Standard.valid_until < today)))
        out["standards_expiring"] = ctx.db.scalar(select(func.count()).select_from(Standard).where(
            *scope, Standard.valid_until >= today, Standard.valid_until <= horizon))
    if ctx.has(P.COMPETENCY_READ):
        out["authorizations_expiring"] = ctx.db.scalar(select(func.count()).select_from(Authorization).where(
            Authorization.organization_id == ctx.organization_id, Authorization.revoked_at.is_(None),
            Authorization.valid_until >= today, Authorization.valid_until <= horizon))
        out["competency_records_expiring"] = ctx.db.scalar(select(func.count()).select_from(CompetencyRecord).where(
            CompetencyRecord.organization_id == ctx.organization_id,
            CompetencyRecord.valid_until >= today, CompetencyRecord.valid_until <= horizon))
    if ctx.has(P.LAB_MANAGE) or ctx.has(P.LAB_EXECUTE):
        scope = [WorkOrder.organization_id == ctx.organization_id]
        if ctx.plant_ids is not None:
            scope.append(WorkOrder.plant_id.in_(ctx.plant_ids))
        out["work_orders_overdue"] = ctx.db.scalar(select(func.count()).select_from(WorkOrder).where(
            *scope, WorkOrder.status.in_(("PENDING", "SCHEDULED", "IN_PROGRESS")), WorkOrder.due_date < today))
    return out
