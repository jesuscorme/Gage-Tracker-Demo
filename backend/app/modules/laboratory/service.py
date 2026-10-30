"""Laboratory Operations.

Request:    SUBMITTED -> APPROVED | REJECTED ; APPROVED -> IN_PROGRESS -> COMPLETED ; -> CANCELLED
Work order: PENDING -> SCHEDULED (re-schedulable) -> IN_PROGRESS -> COMPLETED ; -> CANCELLED

Scheduling rejects incompatible assignments: technician without a current authorization
for the service, technician absent or already booked in an overlapping window, and
equipment (registered gages) that is not available for use, would expire before the job
ends, or is booked by another overlapping work order. Measurements can only be taken
with gages available for use at that moment.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, or_, select

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.sequences import next_code
from app.modules.audit import service as audit
from app.modules.events import service as events
from app.modules.competency import service as competency
from app.modules.documents import service as documents
from app.modules.gages import service as gages
from app.modules.gages.models import Gage
from app.modules.gages.status import AVAILABLE_STATUSES
from app.modules.identity.deps import TenantContext
from app.modules.identity.models import User
from app.modules.identity.permissions import P
from app.modules.laboratory.models import (
    InspectionResult,
    LabService,
    LabSettings,
    MeasurementReport,
    ServiceRequest,
    TechnicianAbsence,
    WorkOrder,
    WorkOrderEvent,
    work_order_equipment,
)
from app.modules.laboratory.report_pdf import render_report
from app.modules.notifications.service import notify, users_with_permission
from app.modules.organizations.models import Department
from app.modules.organizations.router import get_plant

ACTIVE_WO = ("SCHEDULED", "IN_PROGRESS")


# ---------------------------------------------------------------- settings & catalogue


def settings(ctx: TenantContext) -> LabSettings:
    s = ctx.db.get(LabSettings, ctx.organization_id)
    if s is None:
        s = LabSettings(organization_id=ctx.organization_id, hours_per_technician_day=Decimal("8"),
                        working_days=[1, 2, 3, 4, 5])
        ctx.db.add(s)
        ctx.db.flush()
    return s


def save_settings(ctx: TenantContext, data: dict) -> LabSettings:
    s = settings(ctx)
    before = audit.snapshot(s, list(data))
    for k, v in data.items():
        setattr(s, k, v)
    ctx.audit(action="lab.settings_updated", entity_type="lab_settings",
              changes=audit.diff(before, audit.snapshot(s, list(data))))
    ctx.db.commit()
    return s


def get_service(ctx: TenantContext, service_id: uuid.UUID) -> LabService:
    s = ctx.db.scalar(select(LabService).where(LabService.id == service_id,
                                               LabService.organization_id == ctx.organization_id))
    if s is None:
        raise NotFoundError("Service not found")
    return s


def create_service(ctx: TenantContext, data: dict) -> LabService:
    data["code"] = data["code"].strip().upper()
    if ctx.db.scalar(select(LabService.id).where(LabService.organization_id == ctx.organization_id,
                                                 LabService.code == data["code"])):
        raise ConflictError("Service code already exists", code="duplicate_service")
    s = LabService(organization_id=ctx.organization_id, **data)
    ctx.db.add(s)
    ctx.db.flush()
    ctx.audit(action="lab_service.created", entity_type="lab_service", entity_id=s.id,
              changes={k: audit.plain(v) for k, v in data.items()})
    ctx.db.commit()
    return s


def update_service(ctx: TenantContext, service_id: uuid.UUID, data: dict) -> LabService:
    s = get_service(ctx, service_id)
    before = audit.snapshot(s, list(data))
    for k, v in data.items():
        setattr(s, k, v)
    ctx.audit(action="lab_service.updated", entity_type="lab_service", entity_id=s.id,
              changes=audit.diff(before, audit.snapshot(s, list(data))))
    ctx.db.commit()
    return s


def add_absence(ctx: TenantContext, data: dict) -> TechnicianAbsence:
    gages.ensure_active_member(ctx, data["user_id"], "invalid_technician")
    if data["end_date"] < data["start_date"]:
        raise BusinessRuleError("end_date must be on or after start_date", code="invalid_dates")
    a = TechnicianAbsence(organization_id=ctx.organization_id, created_by=ctx.user_id, **data)
    ctx.db.add(a)
    ctx.db.flush()
    ctx.audit(action="lab.absence_registered", entity_type="user", entity_id=data["user_id"],
              changes={k: audit.plain(v) for k, v in data.items()})
    ctx.db.commit()
    return a


# ---------------------------------------------------------------- requests


def own_requests_only(ctx: TenantContext) -> bool:
    """Requesters (no lab management/execution role) only see their own requests and orders."""
    return not (ctx.has(P.LAB_MANAGE) or ctx.has(P.LAB_EXECUTE) or ctx.has(P.LAB_REPORT))


def _scoped_requests(ctx: TenantContext):
    stmt = select(ServiceRequest).where(ServiceRequest.organization_id == ctx.organization_id)
    if ctx.plant_ids is not None:
        stmt = stmt.where(ServiceRequest.plant_id.in_(ctx.plant_ids))
    if own_requests_only(ctx):
        stmt = stmt.where(ServiceRequest.requester_id == ctx.user_id)
    return stmt


def get_request(ctx: TenantContext, request_id: uuid.UUID, *, for_update: bool = False) -> ServiceRequest:
    stmt = _scoped_requests(ctx).where(ServiceRequest.id == request_id)
    if for_update:
        stmt = stmt.with_for_update(of=ServiceRequest)
    r = ctx.db.scalar(stmt)
    if r is None:
        raise NotFoundError("Service request not found")
    return r


def list_requests(ctx: TenantContext, status: list[str] | None, q: str | None) -> list[ServiceRequest]:
    stmt = _scoped_requests(ctx)
    if status:
        stmt = stmt.where(ServiceRequest.status.in_(status))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(ServiceRequest.request_code.ilike(like) | ServiceRequest.part_number.ilike(like)
                          | ServiceRequest.description.ilike(like))
    return list(ctx.db.scalars(stmt.order_by(ServiceRequest.created_at.desc()).limit(500)).unique())


def create_request(ctx: TenantContext, data: dict) -> ServiceRequest:
    get_plant(ctx, data["plant_id"])
    svc = get_service(ctx, data["service_id"])
    if not svc.is_active:
        raise BusinessRuleError("Service is inactive", code="service_inactive")
    if data.get("department_id"):
        d = ctx.db.get(Department, data["department_id"])
        if d is None or d.organization_id != ctx.organization_id or d.plant_id != data["plant_id"]:
            raise BusinessRuleError("Department does not belong to the selected plant", code="department_plant_mismatch")
    if data["requested_date"] < ctx.today():
        raise BusinessRuleError("requested_date cannot be in the past", code="past_date")
    r = ServiceRequest(organization_id=ctx.organization_id, requester_id=ctx.user_id, status="SUBMITTED",
                       request_code=next_code(ctx.db, ctx.organization_id, "SR", ctx.today().year), **data)
    ctx.db.add(r)
    ctx.db.flush()
    ctx.audit(action="lab.request_submitted", entity_type="service_request", entity_id=r.id,
              changes={"request_code": r.request_code} | {k: audit.plain(v) for k, v in data.items()})
    notify(ctx, users_with_permission(ctx, P.LAB_MANAGE), "lab.request_submitted",
           f"New laboratory request {r.request_code}", f"{svc.name} · {r.part_number or ''} · {r.priority}",
           f"/laboratory/requests/{r.id}")
    events.emit(ctx.db, ctx.organization_id, "lab.request_created", "service_request", r.id,
                {"request_code": r.request_code, "service": svc.name, "part_number": r.part_number,
                 "priority": r.priority, "requested_date": r.requested_date})
    ctx.db.commit()
    return get_request(ctx, r.id)


def decide_request(ctx: TenantContext, request_id: uuid.UUID, approve: bool, committed_date: date | None,
                   comment: str | None) -> ServiceRequest:
    r = get_request(ctx, request_id, for_update=True)
    if r.status != "SUBMITTED":
        raise ConflictError(f"Request is {r.status}", code="invalid_request_status")
    if approve:
        if committed_date is None:
            raise BusinessRuleError("Set the committed date", code="committed_date_required")
        if committed_date < ctx.today():
            raise BusinessRuleError("committed_date cannot be in the past", code="past_date")
        r.committed_date = committed_date
    elif not comment:
        raise BusinessRuleError("Explain why the request is rejected", code="reason_required")
    prev = r.status
    r.status = "APPROVED" if approve else "REJECTED"
    r.decision_by, r.decision_at, r.decision_comment = ctx.user_id, datetime.now(UTC), comment
    ctx.audit(action="lab.request_" + ("approved" if approve else "rejected"), entity_type="service_request",
              entity_id=r.id, reason=comment, changes={"status": [prev, r.status],
                                                       "committed_date": audit.plain(committed_date)})
    notify(ctx, [r.requester_id], "lab.request_decided", f"{r.request_code} {r.status.lower()}", comment,
           f"/laboratory/requests/{r.id}")
    ctx.db.commit()
    return r


def cancel_request(ctx: TenantContext, request_id: uuid.UUID, reason: str) -> ServiceRequest:
    r = get_request(ctx, request_id, for_update=True)
    if r.status not in ("SUBMITTED", "APPROVED"):
        raise ConflictError(f"Request is {r.status}", code="invalid_request_status")
    if r.requester_id != ctx.user_id:
        ctx.ensure(P.LAB_MANAGE)
    open_wo = ctx.db.scalar(select(WorkOrder.work_order_code).where(WorkOrder.service_request_id == r.id,
                                                                    WorkOrder.status != "CANCELLED"))
    if open_wo:
        raise ConflictError(f"Cancel work order {open_wo} first", code="work_order_exists")
    prev, r.status = r.status, "CANCELLED"
    ctx.audit(action="lab.request_cancelled", entity_type="service_request", entity_id=r.id, reason=reason,
              changes={"status": [prev, "CANCELLED"]})
    ctx.db.commit()
    return r


# ---------------------------------------------------------------- work orders


def get_work_order(ctx: TenantContext, wo_id: uuid.UUID, *, for_update: bool = False) -> WorkOrder:
    stmt = select(WorkOrder).where(WorkOrder.id == wo_id, WorkOrder.organization_id == ctx.organization_id)
    if for_update:
        stmt = stmt.with_for_update(of=WorkOrder)
    wo = ctx.db.scalar(stmt)
    if wo is None or not ctx.can_access_plant(wo.plant_id):
        raise NotFoundError("Work order not found")
    if own_requests_only(ctx) and wo.request.requester_id != ctx.user_id:
        raise NotFoundError("Work order not found")
    return wo


def _event(ctx: TenantContext, wo: WorkOrder, to: str, comment: str | None = None, data: dict | None = None):
    ctx.db.add(WorkOrderEvent(organization_id=ctx.organization_id, work_order_id=wo.id, from_status=wo.status,
                              to_status=to, comment=comment, data=data, changed_by=ctx.user_id))
    ctx.audit(action=f"lab.work_order_{to.lower()}", entity_type="work_order", entity_id=wo.id, reason=comment,
              changes={"status": [wo.status, to], "work_order_code": wo.work_order_code} | (data or {}))
    wo.status = to


def create_work_order(ctx: TenantContext, request_id: uuid.UUID, planned_hours: Decimal | None,
                      observations: str | None) -> WorkOrder:
    r = get_request(ctx, request_id, for_update=True)
    if r.status != "APPROVED":
        raise ConflictError("Only approved requests can become work orders", code="invalid_request_status")
    if ctx.db.scalar(select(WorkOrder.id).where(WorkOrder.service_request_id == r.id, WorkOrder.status != "CANCELLED")):
        raise ConflictError("The request already has a work order", code="work_order_exists")
    wo = WorkOrder(organization_id=ctx.organization_id, plant_id=r.plant_id, service_request_id=r.id,
                   service_id=r.service_id, priority=r.priority, due_date=r.committed_date, status="PENDING",
                   planned_hours=planned_hours or r.service.standard_hours, observations=observations,
                   created_by=ctx.user_id,
                   work_order_code=next_code(ctx.db, ctx.organization_id, "WO", ctx.today().year))
    ctx.db.add(wo)
    ctx.db.flush()
    ctx.db.add(WorkOrderEvent(organization_id=ctx.organization_id, work_order_id=wo.id, to_status="PENDING",
                              changed_by=ctx.user_id, comment=f"Created from {r.request_code}"))
    ctx.audit(action="lab.work_order_created", entity_type="work_order", entity_id=wo.id,
              changes={"work_order_code": wo.work_order_code, "request": r.request_code})
    ctx.db.commit()
    return get_work_order(ctx, wo.id)


def equipment(ctx: TenantContext, wo: WorkOrder) -> list[Gage]:
    return list(ctx.db.scalars(select(Gage).join(work_order_equipment, work_order_equipment.c.gage_id == Gage.id)
                               .where(work_order_equipment.c.work_order_id == wo.id)).unique())


def _overlaps(start_col, end_col, start: datetime, end: datetime):
    return and_(start_col < end, end_col > start)


def check_schedule(ctx: TenantContext, wo: WorkOrder, technician_id: uuid.UUID, start: datetime, end: datetime,
                   gage_ids: list[uuid.UUID]) -> list[Gage]:
    """Raise if the assignment is incompatible; return the equipment gages."""
    if end <= start:
        raise BusinessRuleError("scheduled_end must be after scheduled_start", code="invalid_schedule")
    gages.ensure_active_member(ctx, technician_id, "invalid_technician")
    competency.ensure_authorized(ctx, technician_id, wo.service.required_activity, on=start.date(),
                                 plant_id=wo.plant_id)
    absent = ctx.db.scalar(select(TechnicianAbsence).where(
        TechnicianAbsence.organization_id == ctx.organization_id, TechnicianAbsence.user_id == technician_id,
        TechnicianAbsence.start_date <= end.date(), TechnicianAbsence.end_date >= start.date()))
    if absent:
        raise ConflictError("The technician is not available in that period", code="technician_absent",
                            details={"from": absent.start_date.isoformat(), "to": absent.end_date.isoformat()})
    clash = ctx.db.scalar(select(WorkOrder.work_order_code).where(
        WorkOrder.organization_id == ctx.organization_id, WorkOrder.technician_id == technician_id,
        WorkOrder.status.in_(ACTIVE_WO), WorkOrder.id != wo.id,
        _overlaps(WorkOrder.scheduled_start, WorkOrder.scheduled_end, start, end)))
    if clash:
        raise ConflictError(f"The technician is already booked on {clash}", code="technician_busy",
                            details={"work_order": clash})

    selected: list[Gage] = []
    for gid in dict.fromkeys(gage_ids):
        g = gages.get_gage(ctx, gid)
        status = gages.current_status(ctx, g)
        if status not in AVAILABLE_STATUSES:
            raise BusinessRuleError(f"{g.gage_code} is {status.value} and cannot be assigned",
                                    code="equipment_unavailable", details={"gage": g.gage_code, "status": status.value})
        if g.next_due_date is None or g.next_due_date < end.date():
            raise BusinessRuleError(f"{g.gage_code} calibration expires before the work ends",
                                    code="equipment_expires", details={"gage": g.gage_code,
                                                                       "next_due_date": audit.plain(g.next_due_date)})
        busy = ctx.db.scalar(select(WorkOrder.work_order_code)
                             .join(work_order_equipment, work_order_equipment.c.work_order_id == WorkOrder.id)
                             .where(work_order_equipment.c.gage_id == g.id, WorkOrder.status.in_(ACTIVE_WO),
                                    WorkOrder.id != wo.id,
                                    _overlaps(WorkOrder.scheduled_start, WorkOrder.scheduled_end, start, end)))
        if busy:
            raise ConflictError(f"{g.gage_code} is booked on {busy}", code="equipment_busy",
                                details={"gage": g.gage_code, "work_order": busy})
        selected.append(g)
    return selected


def schedule(ctx: TenantContext, wo_id: uuid.UUID, data: dict) -> WorkOrder:
    wo = get_work_order(ctx, wo_id, for_update=True)
    if wo.status not in ("PENDING", "SCHEDULED"):
        raise ConflictError(f"Work order is {wo.status}", code="invalid_work_order_status")
    if wo.status == "SCHEDULED" and not data.get("reason"):
        raise BusinessRuleError("Rescheduling needs a reason", code="reason_required")
    start, end = data["scheduled_start"], data["scheduled_end"]
    selected = check_schedule(ctx, wo, data["technician_id"], start, end, data.get("gage_ids", []))
    prev = {"technician_id": audit.plain(wo.technician_id), "start": audit.plain(wo.scheduled_start)}
    wo.technician_id, wo.scheduled_start, wo.scheduled_end = data["technician_id"], start, end
    ctx.db.execute(work_order_equipment.delete().where(work_order_equipment.c.work_order_id == wo.id))
    for g in selected:
        ctx.db.execute(work_order_equipment.insert().values(work_order_id=wo.id, gage_id=g.id))
    _event(ctx, wo, "SCHEDULED", data.get("reason"),
           {"technician_id": str(wo.technician_id), "start": start.isoformat(), "end": end.isoformat(),
            "equipment": [g.gage_code for g in selected], "previous": prev if prev["start"] else None})
    notify(ctx, [wo.technician_id], "lab.work_order_assigned", f"{wo.work_order_code} assigned to you",
           f"{wo.service.name} · {start:%Y-%m-%d %H:%M}", f"/laboratory/work-orders/{wo.id}")
    ctx.db.commit()
    return wo


def start_work_order(ctx: TenantContext, wo_id: uuid.UUID) -> WorkOrder:
    wo = get_work_order(ctx, wo_id, for_update=True)
    if wo.status != "SCHEDULED":
        raise ConflictError(f"Work order is {wo.status}", code="invalid_work_order_status")
    if wo.technician_id != ctx.user_id:
        raise PermissionDeniedError("Only the assigned technician can start the work order",
                                    code="not_assigned_technician")
    competency.ensure_authorized(ctx, ctx.user_id, wo.service.required_activity, plant_id=wo.plant_id)
    wo.started_at = datetime.now(UTC)
    r = wo.request
    if r.status == "APPROVED":
        r.status = "IN_PROGRESS"
    _event(ctx, wo, "IN_PROGRESS")
    ctx.db.commit()
    return wo


def current_results(ctx: TenantContext, wo: WorkOrder) -> list[InspectionResult]:
    return list(ctx.db.scalars(select(InspectionResult).where(
        InspectionResult.work_order_id == wo.id, InspectionResult.superseded.is_(False))
        .order_by(InspectionResult.part_number, InspectionResult.sample_id, InspectionResult.characteristic_number)))


def add_result(ctx: TenantContext, wo_id: uuid.UUID, data: dict) -> InspectionResult:
    wo = get_work_order(ctx, wo_id, for_update=True)
    if wo.status != "IN_PROGRESS":
        raise ConflictError("Results are captured while the work order is in progress",
                            code="invalid_work_order_status")
    competency.ensure_authorized(ctx, ctx.user_id, "DIMENSIONAL_INSPECTION", plant_id=wo.plant_id)
    if data["lower_limit"] > data["upper_limit"]:
        raise BusinessRuleError("lower_limit must be <= upper_limit", code="invalid_limits")
    g = gages.get_gage(ctx, data["gage_id"])
    if g.id not in {x.id for x in equipment(ctx, wo)}:
        raise BusinessRuleError(f"{g.gage_code} is not assigned to this work order", code="equipment_not_assigned")
    status = gages.current_status(ctx, g)
    if status not in AVAILABLE_STATUSES:
        raise BusinessRuleError(f"{g.gage_code} is {status.value}; measurements with it are not allowed",
                                code="equipment_unavailable", details={"gage": g.gage_code, "status": status.value})
    supersedes = None
    if data.get("supersedes_id"):
        supersedes = ctx.db.scalar(select(InspectionResult).where(
            InspectionResult.id == data["supersedes_id"], InspectionResult.work_order_id == wo.id).with_for_update())
        if supersedes is None:
            raise NotFoundError("Result to correct not found")
        if supersedes.superseded:
            raise ConflictError("That result was already corrected", code="already_superseded")
        if not data.get("correction_reason"):
            raise BusinessRuleError("A correction needs a reason", code="reason_required")
        supersedes.superseded = True
    res = InspectionResult(
        organization_id=ctx.organization_id, work_order_id=wo.id, technician_id=ctx.user_id, gage_status=status.value,
        result="OK" if data["lower_limit"] <= data["measured"] <= data["upper_limit"] else "NOK", **data)
    ctx.db.add(res)
    ctx.db.flush()
    ctx.audit(action="lab.result_corrected" if supersedes else "lab.result_recorded", entity_type="work_order",
              entity_id=wo.id, reason=data.get("correction_reason"),
              changes={"characteristic": f"{res.characteristic_number} {res.characteristic}",
                       "measured": audit.plain(res.measured), "result": res.result, "gage": g.gage_code,
                       "previous_measured": audit.plain(supersedes.measured) if supersedes else None})
    ctx.db.commit()
    return res


def complete_work_order(ctx: TenantContext, wo_id: uuid.UUID, observations: str | None) -> WorkOrder:
    wo = get_work_order(ctx, wo_id, for_update=True)
    if wo.status != "IN_PROGRESS":
        raise ConflictError(f"Work order is {wo.status}", code="invalid_work_order_status")
    if wo.technician_id != ctx.user_id:
        ctx.ensure(P.LAB_MANAGE)
    if wo.service.requires_inspection and not current_results(ctx, wo):
        raise BusinessRuleError("Capture the inspection results before completing", code="results_required")
    wo.completed_at = datetime.now(UTC)
    if observations:
        wo.observations = observations
    _event(ctx, wo, "COMPLETED", observations)
    events.emit(ctx.db, ctx.organization_id, "lab.work_order_completed", "work_order", wo.id,
                {"work_order_code": wo.work_order_code, "service_request_id": wo.service_request_id,
                 "results": len(current_results(ctx, wo))})
    ctx.db.commit()
    return wo


def cancel_work_order(ctx: TenantContext, wo_id: uuid.UUID, reason: str) -> WorkOrder:
    wo = get_work_order(ctx, wo_id, for_update=True)
    if wo.status in ("COMPLETED", "CANCELLED"):
        raise ConflictError(f"Work order is {wo.status}", code="invalid_work_order_status")
    wo.cancel_reason = reason
    if wo.request.status == "IN_PROGRESS":
        wo.request.status = "APPROVED"
    _event(ctx, wo, "CANCELLED", reason)
    ctx.db.commit()
    return wo


def list_work_orders(ctx: TenantContext, status: list[str] | None, technician_id: uuid.UUID | None,
                     start: datetime | None, end: datetime | None) -> list[WorkOrder]:
    stmt = select(WorkOrder).where(WorkOrder.organization_id == ctx.organization_id)
    if ctx.plant_ids is not None:
        stmt = stmt.where(WorkOrder.plant_id.in_(ctx.plant_ids))
    if own_requests_only(ctx):
        stmt = stmt.where(WorkOrder.service_request_id.in_(
            select(ServiceRequest.id).where(ServiceRequest.requester_id == ctx.user_id)))
    if status:
        stmt = stmt.where(WorkOrder.status.in_(status))
    if technician_id:
        stmt = stmt.where(WorkOrder.technician_id == technician_id)
    if start and end:
        stmt = stmt.where(_overlaps(WorkOrder.scheduled_start, WorkOrder.scheduled_end, start, end))
    return list(ctx.db.scalars(stmt.order_by(WorkOrder.scheduled_start.asc().nulls_first(),
                                             WorkOrder.created_at.desc()).limit(1000)).unique())


# ---------------------------------------------------------------- reports


def issue_report(ctx: TenantContext, wo_id: uuid.UUID, observations: str | None, revision_reason: str | None) -> MeasurementReport:
    wo = get_work_order(ctx, wo_id, for_update=True)
    if wo.status != "COMPLETED":
        raise ConflictError("Reports are issued for completed work orders", code="invalid_work_order_status")
    if ctx.user_id == wo.technician_id:
        raise BusinessRuleError("The report must be reviewed by someone other than the technician",
                                code="segregation_of_duties")
    competency.ensure_authorized(ctx, ctx.user_id, "TECHNICAL_REVIEW", plant_id=wo.plant_id)
    results = current_results(ctx, wo)
    if not results:
        raise BusinessRuleError("There are no results to report", code="results_required")

    prev = ctx.db.scalar(select(MeasurementReport).where(MeasurementReport.work_order_id == wo.id,
                                                         MeasurementReport.status == "ISSUED").with_for_update())
    if prev and not revision_reason:
        raise BusinessRuleError("Re-issuing a report needs a revision reason", code="reason_required")
    r = wo.request
    names = {i: n for i, n in ctx.db.execute(select(User.id, User.full_name).where(
        User.id.in_({wo.technician_id, ctx.user_id, r.requester_id})))}
    gage_codes = {g.id: g.gage_code for g in ctx.db.scalars(select(Gage).where(
        Gage.id.in_({x.gage_id for x in results}))).unique()}
    acceptance = "ACCEPTED" if all(x.result == "OK" for x in results) else "REJECTED"
    code = prev.report_code if prev else next_code(ctx.db, ctx.organization_id, "MR", ctx.today().year)
    revision = prev.revision + 1 if prev else 0
    snapshot = {
        "report_code": code, "revision": revision, "organization": ctx.organization.name,
        "work_order": wo.work_order_code, "request": r.request_code, "service": wo.service.name,
        "customer_type": r.customer_type, "customer": r.customer_name or names.get(r.requester_id),
        "part_number": r.part_number, "part_revision": r.part_revision, "quantity": r.quantity,
        "technician": names.get(wo.technician_id), "reviewer": names.get(ctx.user_id),
        "issued_on": ctx.today().isoformat(), "acceptance": acceptance, "observations": observations,
        "equipment": sorted(gage_codes.values()), "revision_reason": revision_reason,
        "results": [{
            "part_number": x.part_number, "drawing_revision": x.drawing_revision, "sample": x.sample_id,
            "number": x.characteristic_number, "characteristic": x.characteristic,
            "nominal": audit.plain(x.nominal), "lower": audit.plain(x.lower_limit), "upper": audit.plain(x.upper_limit),
            "measured": audit.plain(x.measured), "unit": x.unit, "gage": gage_codes.get(x.gage_id),
            "result": x.result, "measured_at": x.measured_at.isoformat(),
        } for x in results],
    }
    pdf = render_report(snapshot)
    report = MeasurementReport(organization_id=ctx.organization_id, work_order_id=wo.id, report_code=code,
                               revision=revision, acceptance=acceptance, snapshot=snapshot, observations=observations,
                               revision_reason=revision_reason, technician_id=wo.technician_id,
                               reviewer_id=ctx.user_id, attachment_id=uuid.uuid4())
    att = documents.store(ctx, entity_type="work_order", entity_id=wo.id, category="REPORT",
                          filename=f"{code}-R{revision}.pdf", data=pdf, title=f"{code} rev {revision}", locked=True)
    report.attachment_id = att.id
    if prev:
        prev.status = "SUPERSEDED"
    ctx.db.add(report)
    if r.status in ("APPROVED", "IN_PROGRESS"):
        r.status, r.completed_at = "COMPLETED", datetime.now(UTC)
    ctx.db.flush()
    ctx.audit(action="lab.report_issued", entity_type="work_order", entity_id=wo.id, reason=revision_reason,
              changes={"report": code, "revision": revision, "acceptance": acceptance})
    notify(ctx, [r.requester_id], "lab.report_issued", f"Report {code} rev {revision} issued",
           f"{r.request_code} · {acceptance}", f"/laboratory/reports/{report.id}")
    ctx.db.commit()
    return report


def get_report(ctx: TenantContext, report_id: uuid.UUID) -> MeasurementReport:
    rep = ctx.db.scalar(select(MeasurementReport).where(MeasurementReport.id == report_id,
                                                        MeasurementReport.organization_id == ctx.organization_id))
    if rep is None:
        raise NotFoundError("Report not found")
    get_work_order(ctx, rep.work_order_id)
    return rep


def list_reports(ctx: TenantContext, include_superseded: bool) -> list[MeasurementReport]:
    stmt = (select(MeasurementReport).join(WorkOrder, WorkOrder.id == MeasurementReport.work_order_id)
            .where(MeasurementReport.organization_id == ctx.organization_id))
    if ctx.plant_ids is not None:
        stmt = stmt.where(WorkOrder.plant_id.in_(ctx.plant_ids))
    if own_requests_only(ctx):
        stmt = stmt.where(WorkOrder.service_request_id.in_(
            select(ServiceRequest.id).where(ServiceRequest.requester_id == ctx.user_id)))
    if not include_superseded:
        stmt = stmt.where(MeasurementReport.status == "ISSUED")
    return list(ctx.db.scalars(stmt.order_by(MeasurementReport.issued_at.desc()).limit(500)))


# ---------------------------------------------------------------- KPIs


def _working_days(start: date, days: int, working: list[int]) -> int:
    return sum(1 for i in range(days) if (start + timedelta(days=i)).isoweekday() in working)


def dashboard(ctx: TenantContext) -> dict:
    """Operational KPIs computed from live data (no cached or sample figures)."""
    today = ctx.today()
    scope = [WorkOrder.organization_id == ctx.organization_id]
    if ctx.plant_ids is not None:
        scope.append(WorkOrder.plant_id.in_(ctx.plant_ids))
    req_scope = [ServiceRequest.organization_id == ctx.organization_id]
    if ctx.plant_ids is not None:
        req_scope.append(ServiceRequest.plant_id.in_(ctx.plant_ids))

    wo_counts = dict(ctx.db.execute(select(WorkOrder.status, func.count()).where(*scope).group_by(WorkOrder.status)).all())
    overdue = ctx.db.scalar(select(func.count()).select_from(WorkOrder).where(
        *scope, WorkOrder.status.in_(("PENDING", "SCHEDULED", "IN_PROGRESS")), WorkOrder.due_date < today))
    since = datetime.now(UTC) - timedelta(days=30)
    completed_30 = ctx.db.scalar(select(func.count()).select_from(WorkOrder).where(
        *scope, WorkOrder.status == "COMPLETED", WorkOrder.completed_at >= since))
    pending_requests = ctx.db.scalar(select(func.count()).select_from(ServiceRequest).where(
        *req_scope, ServiceRequest.status == "SUBMITTED"))
    # Response time: request creation -> work order completion (last 90 days).
    rt = ctx.db.execute(select(
        func.avg(func.extract("epoch", WorkOrder.completed_at - ServiceRequest.created_at) / 3600),
        func.count())
        .join(ServiceRequest, ServiceRequest.id == WorkOrder.service_request_id)
        .where(*scope, WorkOrder.status == "COMPLETED",
               WorkOrder.completed_at >= datetime.now(UTC) - timedelta(days=90))).one()
    on_time = ctx.db.scalar(select(func.count()).select_from(WorkOrder).where(
        *scope, WorkOrder.status == "COMPLETED", WorkOrder.completed_at >= since,
        or_(WorkOrder.due_date.is_(None), func.date(WorkOrder.completed_at) <= WorkOrder.due_date)))

    # Load per technician for the next 7 days, and capacity utilisation.
    s = settings(ctx)
    horizon_start = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    horizon_end = horizon_start + timedelta(days=7)
    load_rows = ctx.db.execute(
        select(WorkOrder.technician_id, User.full_name, func.count(), func.coalesce(func.sum(WorkOrder.planned_hours), 0))
        .join(User, User.id == WorkOrder.technician_id)
        .where(*scope, WorkOrder.status.in_(ACTIVE_WO),
               _overlaps(WorkOrder.scheduled_start, WorkOrder.scheduled_end, horizon_start, horizon_end))
        .group_by(WorkOrder.technician_id, User.full_name).order_by(User.full_name)).all()
    lab_techs = competency.authorized_users(ctx, "LAB_SERVICE", None, None)
    tech_ids = {u.id for u in lab_techs} | {r[0] for r in load_rows}
    days = _working_days(today, 7, s.working_days)
    capacity_hours = Decimal(days) * s.hours_per_technician_day * len(tech_ids)
    planned = sum((Decimal(r[3]) for r in load_rows), Decimal(0))
    return {
        "as_of": today.isoformat(),
        "pending_requests": pending_requests,
        "work_orders": {k: wo_counts.get(k, 0) for k in ("PENDING", "SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED")},
        "open_work_orders": sum(wo_counts.get(k, 0) for k in ("PENDING", "SCHEDULED", "IN_PROGRESS")),
        "overdue_work_orders": overdue,
        "completed_last_30_days": completed_30,
        "on_time_rate_30_days": round(on_time / completed_30 * 100, 1) if completed_30 else None,
        "avg_response_hours_90_days": round(float(rt[0]), 1) if rt[0] is not None else None,
        "completed_sample_90_days": rt[1],
        "workload_next_7_days": [
            {"technician_id": str(r[0]), "technician": r[1], "work_orders": r[2], "planned_hours": float(r[3])}
            for r in load_rows],
        "capacity": {"working_days": days, "technicians": len(tech_ids),
                     "hours_per_day": float(s.hours_per_technician_day), "capacity_hours": float(capacity_hours),
                     "planned_hours": float(planned),
                     "utilization_pct": round(float(planned / capacity_hours * 100), 1) if capacity_hours else None},
    }
