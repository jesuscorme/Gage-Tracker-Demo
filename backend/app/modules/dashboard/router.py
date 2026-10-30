import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.errors import BusinessRuleError, NotFoundError
from app.modules.dashboard import service
from app.modules.gages import service as gages
from app.modules.gages.models import Gage
from app.modules.gages.schemas import GageOut
from app.modules.gages.status import AVAILABLE_STATUSES, ControlStatus, GageStatus
from app.modules.identity.deps import TenantContext, require
from app.modules.identity.permissions import P
from app.modules.organizations.models import Plant

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardSummary(BaseModel):
    as_of: date
    due_soon_days: int
    # Plants included in the figures: null = every plant of the organization.
    plant_scope: list[str] | None
    total_in_service: int
    available: int
    by_status: dict[str, int]
    upcoming: list[GageOut]


@router.get("/summary", response_model=DashboardSummary)
def summary(ctx: TenantContext = Depends(require(P.GAGES_READ))):
    """Gage KPIs computed live from the gage table, within the user's plant scope."""
    counts = gages.status_counts(ctx)
    in_service = sum(n for s, n in counts.items() if s != GageStatus.INACTIVE)
    horizon = ctx.today() + timedelta(days=ctx.organization.due_soon_days)
    stmt = (
        gages.scoped_query(ctx)
        .where(Gage.control_status == ControlStatus.ACTIVE.value)
        .where((Gage.next_due_date.is_(None)) | (Gage.next_due_date <= horizon))
        .order_by(Gage.next_due_date.asc().nulls_first(), Gage.gage_code)
        .limit(10)
    )
    upcoming = [gages.to_out(ctx, g) for g in ctx.db.scalars(stmt).unique()]
    return DashboardSummary(
        as_of=ctx.today(),
        due_soon_days=ctx.organization.due_soon_days,
        plant_scope=None if ctx.plant_ids is None else sorted(str(p) for p in ctx.plant_ids),
        total_in_service=in_service,
        available=sum(counts[s.value] for s in AVAILABLE_STATUSES),
        by_status=counts,
        upcoming=upcoming,
    )


@router.get("/overview")
def overview(
    plant_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    gage_type_id: uuid.UUID | None = None,
    status: GageStatus | None = None,
    responsible_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    ctx: TenantContext = Depends(require(P.GAGES_READ)),
):
    """Executive dashboard. Filters apply to the gage population; out-of-scope plants are not found."""
    if plant_id:
        plant = ctx.db.get(Plant, plant_id)
        if plant is None or plant.organization_id != ctx.organization_id or not ctx.can_access_plant(plant_id):
            raise NotFoundError("Plant not found")
    if date_from and date_to and date_from > date_to:
        raise BusinessRuleError("date_from must not be after date_to", code="invalid_period")
    if date_from and date_to and (date_to - date_from).days > 731:
        raise BusinessRuleError("The period cannot exceed two years", code="invalid_period")
    return service.overview(ctx, service.Filters(
        plant_id=plant_id, department_id=department_id, gage_type_id=gage_type_id,
        status=status.value if status else None, responsible_id=responsible_id, date_from=date_from, date_to=date_to))
