import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.modules.audit.router import AuditPage, query_events
from app.modules.gages import service
from app.modules.gages.schemas import (
    GageCreate,
    GageOut,
    GagePage,
    GageTransitionIn,
    GageTypeIn,
    GageTypeOut,
    GageTypeUpdate,
    GageUpdate,
    StatusHistoryOut,
)
from app.modules.gages.status import GageStatus
from app.modules.identity.deps import TenantContext, require
from app.modules.identity.models import User
from app.modules.identity.permissions import P

router = APIRouter(tags=["gages"])


# ---------------------------------------------------------------- gage types


@router.get("/gage-types", response_model=list[GageTypeOut])
def list_gage_types(include_inactive: bool = False, ctx: TenantContext = Depends(require(P.GAGES_READ))):
    return service.list_gage_types(ctx, include_inactive)


@router.post("/gage-types", response_model=GageTypeOut, status_code=201)
def create_gage_type(body: GageTypeIn, ctx: TenantContext = Depends(require(P.GAGE_TYPES_MANAGE))):
    return service.create_gage_type(ctx, body)


@router.patch("/gage-types/{type_id}", response_model=GageTypeOut)
def update_gage_type(type_id: uuid.UUID, body: GageTypeUpdate,
                     ctx: TenantContext = Depends(require(P.GAGE_TYPES_MANAGE))):
    return service.update_gage_type(ctx, type_id, body)


# ---------------------------------------------------------------- gages


@router.get("/gages", response_model=GagePage)
def list_gages(
    q: str | None = Query(None, max_length=100),
    status: list[GageStatus] | None = Query(None),
    plant_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    gage_type_id: uuid.UUID | None = None,
    available: bool | None = None,
    include_inactive: bool = False,
    sort: str = "gage_code",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    ctx: TenantContext = Depends(require(P.GAGES_READ)),
):
    rows, total = service.list_gages(
        ctx, q=q, statuses=status, plant_id=plant_id, department_id=department_id,
        gage_type_id=gage_type_id, available=available, include_inactive=include_inactive,
        sort=sort, page=page, page_size=page_size,
    )
    return GagePage(items=[service.to_out(ctx, g) for g in rows], total=total, page=page, page_size=page_size)


@router.post("/gages", response_model=GageOut, status_code=201)
def create_gage(body: GageCreate, ctx: TenantContext = Depends(require(P.GAGES_CREATE))):
    return service.to_out(ctx, service.create_gage(ctx, body))


@router.get("/gages/{gage_id}", response_model=GageOut)
def get_gage(gage_id: uuid.UUID, ctx: TenantContext = Depends(require(P.GAGES_READ))):
    return service.to_out(ctx, service.get_gage(ctx, gage_id))


@router.patch("/gages/{gage_id}", response_model=GageOut)
def update_gage(gage_id: uuid.UUID, body: GageUpdate, ctx: TenantContext = Depends(require(P.GAGES_UPDATE))):
    return service.to_out(ctx, service.update_gage(ctx, gage_id, body))


@router.post("/gages/{gage_id}/transitions", response_model=GageOut)
def transition_gage(gage_id: uuid.UUID, body: GageTransitionIn,
                    ctx: TenantContext = Depends(require(P.GAGES_READ))):
    """Change the controlled status. The required permission depends on the transition."""
    return service.to_out(ctx, service.transition_gage(ctx, gage_id, body))


@router.get("/gages/{gage_id}/status-history", response_model=list[StatusHistoryOut])
def gage_status_history(gage_id: uuid.UUID, ctx: TenantContext = Depends(require(P.GAGES_READ))):
    rows = service.status_history(ctx, gage_id)
    ids = {r.changed_by for r in rows if r.changed_by}
    names = {i: n for i, n in ctx.db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))} if ids else {}
    return [StatusHistoryOut.model_validate(r).model_copy(update={"changed_by_name": names.get(r.changed_by)})
            for r in rows]


@router.get("/gages/{gage_id}/audit", response_model=AuditPage)
def gage_audit(
    gage_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: TenantContext = Depends(require(P.GAGES_READ)),
):
    """Change history of one gage (readable by anyone who can read the gage)."""
    service.get_gage(ctx, gage_id)
    return query_events(ctx.db, ctx.organization_id, entity_type="gage", entity_id=str(gage_id),
                        limit=limit, offset=offset)
