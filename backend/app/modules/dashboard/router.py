from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.modules.gages import service as gages
from app.modules.gages.models import Gage
from app.modules.gages.schemas import GageOut
from app.modules.gages.status import AVAILABLE_STATUSES, ControlStatus, GageStatus
from app.modules.identity.deps import TenantContext, require
from app.modules.identity.permissions import P

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
