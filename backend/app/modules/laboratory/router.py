import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator
from sqlalchemy import select

from app.modules.documents import service as documents
from app.modules.gages import service as gages
from app.modules.identity.deps import TenantContext, require
from app.modules.identity.models import User
from app.modules.identity.permissions import P
from app.modules.laboratory import service
from app.modules.laboratory.models import (
    PRIORITIES,
    REQUEST_STATUSES,
    WO_STATUSES,
    InspectionResult,
    LabService,
    MeasurementReport,
    ServiceRequest,
    TechnicianAbsence,
    WorkOrder,
    WorkOrderEvent,
)

router = APIRouter(prefix="/lab", tags=["laboratory"])
documents.register("service_request", P.LAB_READ, P.LAB_READ, lambda ctx, i: service.get_request(ctx, i))
documents.register("work_order", P.LAB_READ, P.LAB_EXECUTE, lambda ctx, i: service.get_work_order(ctx, i))

Priority = Literal[PRIORITIES]  # type: ignore[valid-type]
ReqStatus = Literal[REQUEST_STATUSES]  # type: ignore[valid-type]
WoStatus = Literal[WO_STATUSES]  # type: ignore[valid-type]


def _dec(v):
    return None if v is None else format(v.normalize(), "f")


def _aware(v: datetime) -> datetime:
    if v.tzinfo is None:
        raise ValueError("datetime must include a time zone offset")
    return v


# ---------------------------------------------------------------- schemas


class ServiceIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    standard_hours: Decimal = Field(gt=0, le=1000, decimal_places=2)
    required_activity: Literal["LAB_SERVICE", "DIMENSIONAL_INSPECTION"] = "LAB_SERVICE"
    requires_inspection: bool = True


class ServiceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    standard_hours: Decimal | None = Field(default=None, gt=0, le=1000, decimal_places=2)
    requires_inspection: bool | None = None
    is_active: bool | None = None


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    standard_hours: Decimal
    required_activity: str
    requires_inspection: bool
    is_active: bool

    @field_serializer("standard_hours")
    def _d(self, v):
        return _dec(v)


class SettingsIn(BaseModel):
    hours_per_technician_day: Decimal = Field(gt=0, le=24, decimal_places=2)
    working_days: list[int] = Field(min_length=1, max_length=7)

    @field_validator("working_days")
    @classmethod
    def _days(cls, v):
        if any(d < 1 or d > 7 for d in v):
            raise ValueError("working days are ISO weekdays 1..7")
        return sorted(set(v))


class AbsenceIn(BaseModel):
    user_id: uuid.UUID
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=200)


class AbsenceOut(AbsenceIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_name: str | None = None


class RequestIn(BaseModel):
    plant_id: uuid.UUID
    department_id: uuid.UUID | None = None
    service_id: uuid.UUID
    customer_type: Literal["INTERNAL", "EXTERNAL"] = "INTERNAL"
    customer_name: str | None = Field(default=None, max_length=200)
    part_number: str | None = Field(default=None, max_length=80)
    part_revision: str | None = Field(default=None, max_length=20)
    quantity: int = Field(default=1, ge=1, le=100000)
    description: str = Field(min_length=3, max_length=2000)
    priority: Priority = "NORMAL"
    requested_date: date


class DecisionIn(BaseModel):
    approve: bool
    committed_date: date | None = None
    comment: str | None = Field(default=None, max_length=1000)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    request_code: str
    plant_id: uuid.UUID
    department_id: uuid.UUID | None
    requester_id: uuid.UUID
    requester_name: str | None = None
    customer_type: str
    customer_name: str | None
    service_id: uuid.UUID
    service_name: str = ""
    part_number: str | None
    part_revision: str | None
    quantity: int
    description: str
    priority: str
    requested_date: date
    committed_date: date | None
    status: str
    decision_comment: str | None
    decision_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    work_order_id: uuid.UUID | None = None
    work_order_code: str | None = None


class WorkOrderIn(BaseModel):
    service_request_id: uuid.UUID
    planned_hours: Decimal | None = Field(default=None, gt=0, le=1000, decimal_places=2)
    observations: str | None = Field(default=None, max_length=4000)


class ScheduleIn(BaseModel):
    technician_id: uuid.UUID
    scheduled_start: datetime
    scheduled_end: datetime
    gage_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    reason: str | None = Field(default=None, max_length=1000)

    _tz = field_validator("scheduled_start", "scheduled_end")(_aware)


class CompleteIn(BaseModel):
    observations: str | None = Field(default=None, max_length=4000)


class ResultIn(BaseModel):
    part_number: str = Field(min_length=1, max_length=80)
    drawing_revision: str | None = Field(default=None, max_length=20)
    sample_id: str | None = Field(default=None, max_length=40)
    characteristic_number: str = Field(min_length=1, max_length=20)
    characteristic: str = Field(min_length=1, max_length=200)
    nominal: Decimal = Field(max_digits=18, decimal_places=6)
    lower_limit: Decimal = Field(max_digits=18, decimal_places=6)
    upper_limit: Decimal = Field(max_digits=18, decimal_places=6)
    measured: Decimal = Field(max_digits=18, decimal_places=6)
    unit: str = Field(min_length=1, max_length=20)
    gage_id: uuid.UUID
    supersedes_id: uuid.UUID | None = None
    correction_reason: str | None = Field(default=None, max_length=500)


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    part_number: str
    drawing_revision: str | None
    sample_id: str | None
    characteristic_number: str
    characteristic: str
    nominal: Decimal
    lower_limit: Decimal
    upper_limit: Decimal
    measured: Decimal
    unit: str
    gage_id: uuid.UUID
    gage_code: str | None = None
    gage_status: str
    technician_id: uuid.UUID
    measured_at: datetime
    result: str
    superseded: bool
    supersedes_id: uuid.UUID | None
    correction_reason: str | None

    @field_serializer("nominal", "lower_limit", "upper_limit", "measured")
    def _d(self, v):
        return _dec(v)


class ReportIn(BaseModel):
    observations: str | None = Field(default=None, max_length=4000)
    revision_reason: str | None = Field(default=None, max_length=500)


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    work_order_id: uuid.UUID
    report_code: str
    revision: int
    status: str
    acceptance: str
    snapshot: dict
    observations: str | None
    revision_reason: str | None
    issued_at: datetime
    attachment_id: uuid.UUID


class WorkOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    work_order_code: str
    service_request_id: uuid.UUID
    request_code: str = ""
    service_id: uuid.UUID
    service_name: str = ""
    part_number: str | None = None
    plant_id: uuid.UUID
    status: str
    priority: str
    planned_hours: Decimal
    technician_id: uuid.UUID | None
    technician_name: str | None = None
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    due_date: date | None
    overdue: bool = False
    observations: str | None
    cancel_reason: str | None
    created_at: datetime

    @field_serializer("planned_hours")
    def _d(self, v):
        return _dec(v)


class EquipmentOut(BaseModel):
    id: uuid.UUID
    gage_code: str
    description: str
    status: str
    next_due_date: date | None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    from_status: str | None
    to_status: str
    comment: str | None
    data: dict | None
    changed_by_name: str | None = None
    changed_at: datetime


class WorkOrderDetail(WorkOrderOut):
    request: RequestOut
    requires_inspection: bool
    required_activity: str
    equipment: list[EquipmentOut]
    results: list[ResultOut]
    events: list[EventOut]
    reports: list[ReportOut]


# ---------------------------------------------------------------- mapping helpers


def _names(ctx: TenantContext, ids) -> dict:
    ids = {i for i in ids if i}
    return {i: n for i, n in ctx.db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))} if ids else {}


def requests_out(ctx: TenantContext, rows: list[ServiceRequest]) -> list[RequestOut]:
    names = _names(ctx, [r.requester_id for r in rows])
    wos = {w.service_request_id: w for w in ctx.db.scalars(select(WorkOrder).where(
        WorkOrder.service_request_id.in_([r.id for r in rows]), WorkOrder.status != "CANCELLED")).unique()} if rows else {}
    return [RequestOut.model_validate(r).model_copy(update={
        "requester_name": names.get(r.requester_id), "service_name": r.service.name,
        "work_order_id": wos[r.id].id if r.id in wos else None,
        "work_order_code": wos[r.id].work_order_code if r.id in wos else None}) for r in rows]


def wo_out(ctx: TenantContext, rows: list[WorkOrder]) -> list[WorkOrderOut]:
    names = _names(ctx, [w.technician_id for w in rows])
    today = ctx.today()
    return [WorkOrderOut.model_validate(w).model_copy(update={
        "request_code": w.request.request_code, "service_name": w.service.name, "part_number": w.request.part_number,
        "technician_name": names.get(w.technician_id),
        "overdue": bool(w.due_date and w.due_date < today and w.status in ("PENDING", "SCHEDULED", "IN_PROGRESS")),
    }) for w in rows]


def wo_detail(ctx: TenantContext, wo: WorkOrder) -> WorkOrderDetail:
    ctx.db.refresh(wo)
    eq = service.equipment(ctx, wo)
    results = list(ctx.db.scalars(select(InspectionResult).where(InspectionResult.work_order_id == wo.id)
                                  .order_by(InspectionResult.part_number, InspectionResult.sample_id,
                                            InspectionResult.characteristic_number, InspectionResult.measured_at)))
    codes = {g.id: g.gage_code for g in eq}
    events = list(ctx.db.scalars(select(WorkOrderEvent).where(WorkOrderEvent.work_order_id == wo.id)
                                 .order_by(WorkOrderEvent.changed_at.desc())))
    names = _names(ctx, [e.changed_by for e in events])
    reports = list(ctx.db.scalars(select(MeasurementReport).where(MeasurementReport.work_order_id == wo.id)
                                  .order_by(MeasurementReport.revision.desc())))
    return WorkOrderDetail(
        **wo_out(ctx, [wo])[0].model_dump(),
        request=requests_out(ctx, [wo.request])[0],
        requires_inspection=wo.service.requires_inspection,
        required_activity=wo.service.required_activity,
        equipment=[EquipmentOut(id=g.id, gage_code=g.gage_code, description=g.description,
                                status=gages.current_status(ctx, g).value, next_due_date=g.next_due_date) for g in eq],
        results=[ResultOut.model_validate(r).model_copy(update={"gage_code": codes.get(r.gage_id)}) for r in results],
        events=[EventOut.model_validate(e).model_copy(update={"changed_by_name": names.get(e.changed_by)}) for e in events],
        reports=[ReportOut.model_validate(r) for r in reports],
    )


# ---------------------------------------------------------------- settings, services, absences


@router.get("/dashboard")
def lab_dashboard(ctx: TenantContext = Depends(require(P.LAB_READ))):
    return service.dashboard(ctx)


@router.get("/settings")
def get_settings(ctx: TenantContext = Depends(require(P.LAB_READ))):
    s = service.settings(ctx)
    ctx.db.commit()
    return {"hours_per_technician_day": float(s.hours_per_technician_day), "working_days": s.working_days}


@router.put("/settings")
def put_settings(body: SettingsIn, ctx: TenantContext = Depends(require(P.LAB_MANAGE))):
    s = service.save_settings(ctx, body.model_dump())
    return {"hours_per_technician_day": float(s.hours_per_technician_day), "working_days": s.working_days}


@router.get("/services", response_model=list[ServiceOut])
def list_services(include_inactive: bool = False, ctx: TenantContext = Depends(require(P.LAB_READ))):
    stmt = select(LabService).where(LabService.organization_id == ctx.organization_id)
    if not include_inactive:
        stmt = stmt.where(LabService.is_active.is_(True))
    return list(ctx.db.scalars(stmt.order_by(LabService.name)))


@router.post("/services", response_model=ServiceOut, status_code=201)
def create_service(body: ServiceIn, ctx: TenantContext = Depends(require(P.LAB_MANAGE))):
    return service.create_service(ctx, body.model_dump())


@router.patch("/services/{service_id}", response_model=ServiceOut)
def update_service(service_id: uuid.UUID, body: ServiceUpdate, ctx: TenantContext = Depends(require(P.LAB_MANAGE))):
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items()
            if not (k in ("name", "standard_hours", "requires_inspection", "is_active") and v is None)}
    return service.update_service(ctx, service_id, data)


@router.get("/absences", response_model=list[AbsenceOut])
def list_absences(ctx: TenantContext = Depends(require(P.LAB_READ))):
    rows = list(ctx.db.scalars(select(TechnicianAbsence).where(
        TechnicianAbsence.organization_id == ctx.organization_id,
        TechnicianAbsence.end_date >= ctx.today()).order_by(TechnicianAbsence.start_date)))
    names = _names(ctx, [a.user_id for a in rows])
    return [AbsenceOut.model_validate(a).model_copy(update={"user_name": names.get(a.user_id)}) for a in rows]


@router.post("/absences", response_model=AbsenceOut, status_code=201)
def add_absence(body: AbsenceIn, ctx: TenantContext = Depends(require(P.LAB_MANAGE))):
    return service.add_absence(ctx, body.model_dump())


# ---------------------------------------------------------------- requests


@router.get("/requests", response_model=list[RequestOut])
def list_requests(status: list[ReqStatus] | None = Query(None), q: str | None = Query(None, max_length=100),
                  ctx: TenantContext = Depends(require(P.LAB_READ))):
    return requests_out(ctx, service.list_requests(ctx, status, q))


@router.post("/requests", response_model=RequestOut, status_code=201)
def create_request(body: RequestIn, ctx: TenantContext = Depends(require(P.LAB_REQUEST))):
    return requests_out(ctx, [service.create_request(ctx, body.model_dump())])[0]


@router.get("/requests/{request_id}", response_model=RequestOut)
def get_request(request_id: uuid.UUID, ctx: TenantContext = Depends(require(P.LAB_READ))):
    return requests_out(ctx, [service.get_request(ctx, request_id)])[0]


@router.post("/requests/{request_id}/decision", response_model=RequestOut)
def decide_request(request_id: uuid.UUID, body: DecisionIn, ctx: TenantContext = Depends(require(P.LAB_MANAGE))):
    return requests_out(ctx, [service.decide_request(ctx, request_id, body.approve, body.committed_date,
                                                     body.comment)])[0]


@router.post("/requests/{request_id}/cancel", response_model=RequestOut)
def cancel_request(request_id: uuid.UUID, body: ReasonIn, ctx: TenantContext = Depends(require(P.LAB_READ))):
    return requests_out(ctx, [service.cancel_request(ctx, request_id, body.reason)])[0]


# ---------------------------------------------------------------- work orders


@router.get("/work-orders", response_model=list[WorkOrderOut])
def list_work_orders(status: list[WoStatus] | None = Query(None), technician_id: uuid.UUID | None = None,
                     start: datetime | None = None, end: datetime | None = None,
                     ctx: TenantContext = Depends(require(P.LAB_READ))):
    return wo_out(ctx, service.list_work_orders(ctx, status, technician_id, start, end))


@router.post("/work-orders", response_model=WorkOrderDetail, status_code=201)
def create_work_order(body: WorkOrderIn, ctx: TenantContext = Depends(require(P.LAB_MANAGE))):
    return wo_detail(ctx, service.create_work_order(ctx, body.service_request_id, body.planned_hours, body.observations))


@router.get("/work-orders/{wo_id}", response_model=WorkOrderDetail)
def get_work_order(wo_id: uuid.UUID, ctx: TenantContext = Depends(require(P.LAB_READ))):
    return wo_detail(ctx, service.get_work_order(ctx, wo_id))


@router.post("/work-orders/{wo_id}/schedule", response_model=WorkOrderDetail)
def schedule_work_order(wo_id: uuid.UUID, body: ScheduleIn, ctx: TenantContext = Depends(require(P.LAB_MANAGE))):
    return wo_detail(ctx, service.schedule(ctx, wo_id, body.model_dump()))


@router.post("/work-orders/{wo_id}/start", response_model=WorkOrderDetail)
def start_work_order(wo_id: uuid.UUID, ctx: TenantContext = Depends(require(P.LAB_EXECUTE))):
    return wo_detail(ctx, service.start_work_order(ctx, wo_id))


@router.post("/work-orders/{wo_id}/results", response_model=WorkOrderDetail, status_code=201)
def add_result(wo_id: uuid.UUID, body: ResultIn, ctx: TenantContext = Depends(require(P.LAB_EXECUTE))):
    service.add_result(ctx, wo_id, body.model_dump())
    return wo_detail(ctx, service.get_work_order(ctx, wo_id))


@router.post("/work-orders/{wo_id}/complete", response_model=WorkOrderDetail)
def complete_work_order(wo_id: uuid.UUID, body: CompleteIn, ctx: TenantContext = Depends(require(P.LAB_EXECUTE))):
    return wo_detail(ctx, service.complete_work_order(ctx, wo_id, body.observations))


@router.post("/work-orders/{wo_id}/cancel", response_model=WorkOrderDetail)
def cancel_work_order(wo_id: uuid.UUID, body: ReasonIn, ctx: TenantContext = Depends(require(P.LAB_MANAGE))):
    return wo_detail(ctx, service.cancel_work_order(ctx, wo_id, body.reason))


@router.post("/work-orders/{wo_id}/reports", response_model=ReportOut, status_code=201)
def issue_report(wo_id: uuid.UUID, body: ReportIn, ctx: TenantContext = Depends(require(P.LAB_REPORT))):
    return service.issue_report(ctx, wo_id, body.observations, body.revision_reason)


# ---------------------------------------------------------------- reports


@router.get("/reports", response_model=list[ReportOut])
def list_reports(include_superseded: bool = False, ctx: TenantContext = Depends(require(P.LAB_READ))):
    return service.list_reports(ctx, include_superseded)


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: uuid.UUID, ctx: TenantContext = Depends(require(P.LAB_READ))):
    return service.get_report(ctx, report_id)
