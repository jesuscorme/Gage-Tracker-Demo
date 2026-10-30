"""Report catalogue: each report is a column list plus a query over the operational tables.

Queries always apply tenant and plant scope and the common filters (plant, period,
status, gage). Rows are plain dicts; the renderers turn them into PDF / XLSX / CSV / JSON.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import and_, func, select

from app.core.errors import BusinessRuleError
from app.modules.audit.service import plain
from app.modules.calibration.models import CalibrationActivity, CalibrationCertificate, CalibrationPoint
from app.modules.gages import service as gages
from app.modules.gages.models import Gage, GageMovement, GageStatusHistory, GageType
from app.modules.identity.deps import TenantContext
from app.modules.identity.models import User
from app.modules.identity.permissions import P
from app.modules.laboratory.models import (InspectionResult, LabService, LabSettings, MeasurementReport,
                                           ServiceRequest, WorkOrder)
from app.modules.msa.models import MsaRun, MsaStudy
from app.modules.oot.models import OotAction, OotCase, OotImpactItem
from app.modules.organizations.models import Plant
from app.modules.standards.models import Standard, StandardCertificate


@dataclass
class Params:
    plant_id: uuid.UUID | None = None
    date_from: date | None = None
    date_to: date | None = None
    status: str | None = None
    gage_id: uuid.UUID | None = None


@dataclass(frozen=True)
class Column:
    key: str
    es: str
    en: str


@dataclass
class Report:
    key: str
    group: str                  # METROLOGY | MSA | LAB | OOT
    es: str
    en: str
    permission: str
    columns: list[Column]
    query: Callable[[TenantContext, Params], list[dict]] = field(repr=False)
    needs_gage: bool = False
    uses_period: bool = False


def C(key, es, en=None):
    return Column(key, es, en or es)


def _period(p: Params, ctx: TenantContext) -> tuple[date, date, datetime, datetime]:
    d_to = p.date_to or ctx.today()
    d_from = p.date_from or (d_to - timedelta(days=365))
    if d_from > d_to:
        raise BusinessRuleError("date_from must not be after date_to", code="invalid_period")
    return d_from, d_to, datetime.combine(d_from, time.min, tzinfo=UTC), \
        datetime.combine(d_to + timedelta(days=1), time.min, tzinfo=UTC)


def _plant_scope(ctx: TenantContext, p: Params, col):
    conds = []
    if ctx.plant_ids is not None:
        conds.append(col.in_(ctx.plant_ids))
    if p.plant_id:
        conds.append(col == p.plant_id)
    return and_(*conds) if conds else and_(True)


def _rows(result) -> list[dict]:
    return [{k: plain(v) for k, v in r._mapping.items()} for r in result]


def _users():
    return User.__table__.alias()


# ---------------------------------------------------------------- metrology

def gage_inventory(ctx, p):
    st = gages._status_sql(ctx).label("status")
    resp = _users()
    q = (select(Gage.gage_code, Gage.description, GageType.code.label("type"), Plant.code.label("plant"),
                Gage.location, Gage.manufacturer, Gage.model, Gage.serial_number, Gage.criticality,
                resp.c.full_name.label("responsible"), Gage.calibration_frequency_days.label("frequency_days"),
                Gage.last_calibration_date, Gage.next_due_date, st)
         .join(GageType, GageType.id == Gage.gage_type_id).join(Plant, Plant.id == Gage.plant_id)
         .outerjoin(resp, resp.c.id == Gage.responsible_user_id)
         .where(Gage.organization_id == ctx.organization_id, _plant_scope(ctx, p, Gage.plant_id)))
    if p.status:
        q = q.where(gages._status_sql(ctx) == p.status)
    return _rows(ctx.db.execute(q.order_by(Gage.gage_code)))


def gage_history(ctx, p):
    g = gages.get_gage(ctx, p.gage_id)
    events = []
    for h in ctx.db.scalars(select(GageStatusHistory).where(GageStatusHistory.gage_id == g.id)):
        events.append({"date": plain(h.changed_at), "event": "STATUS", "detail": f"{h.from_status or '—'} → {h.to_status}",
                       "reason": h.reason})
    for m in ctx.db.scalars(select(GageMovement).where(GageMovement.gage_id == g.id)):
        events.append({"date": plain(m.moved_at), "event": "TRANSFER",
                       "detail": ", ".join(f"{k}: {v[0]} → {v[1]}" if isinstance(v, list) else f"{k}: {v}"
                                           for k, v in (m.changes or {}).items()), "reason": m.reason})
    for a in ctx.db.scalars(select(CalibrationActivity).where(CalibrationActivity.gage_id == g.id)):
        events.append({"date": plain(a.released_at or a.created_at), "event": a.activity_type,
                       "detail": f"{a.calibration_code} · {a.status} · {a.result or '—'}", "reason": a.observations})
    for c in ctx.db.scalars(select(OotCase).where(OotCase.gage_id == g.id)):
        events.append({"date": plain(c.created_at), "event": "OOT", "detail": f"{c.case_code} · {c.status}",
                       "reason": c.found_result})
    return sorted(events, key=lambda e: e["date"] or "")


def calibration_program(ctx, p):
    d_from, d_to, *_ = _period(p, ctx)
    st = gages._status_sql(ctx).label("status")
    planned = select(CalibrationActivity.calibration_code, CalibrationActivity.gage_id, CalibrationActivity.planned_date,
                     CalibrationActivity.scheduled_date, CalibrationActivity.status) \
        .where(CalibrationActivity.status.not_in(("RELEASED", "CANCELLED"))).subquery()
    q = (select(Gage.gage_code, Gage.description, Plant.code.label("plant"), Gage.next_due_date, st,
                planned.c.calibration_code, planned.c.planned_date, planned.c.scheduled_date,
                planned.c.status.label("activity_status"))
         .join(Plant, Plant.id == Gage.plant_id).outerjoin(planned, planned.c.gage_id == Gage.id)
         .where(Gage.organization_id == ctx.organization_id, _plant_scope(ctx, p, Gage.plant_id),
                Gage.control_status != "INACTIVE", Gage.next_due_date <= d_to))
    return _rows(ctx.db.execute(q.order_by(Gage.next_due_date, Gage.gage_code)))


def calibrations_overdue(ctx, p):
    p2 = Params(**{**p.__dict__, "status": "OVERDUE"})
    rows = gage_inventory(ctx, p2)
    today = ctx.today()
    for r in rows:
        r["days_overdue"] = (today - date.fromisoformat(r["next_due_date"])).days if r["next_due_date"] else None
    return rows


def _released(ctx, p):
    d_from, d_to, *_ = _period(p, ctx)
    return and_(CalibrationActivity.organization_id == ctx.organization_id, CalibrationActivity.status == "RELEASED",
                CalibrationActivity.performed_date >= d_from, CalibrationActivity.performed_date <= d_to,
                _plant_scope(ctx, p, CalibrationActivity.plant_id))


def calibrations_performed(ctx, p):
    tech, rev, appr = _users(), _users(), _users()
    q = (select(CalibrationActivity.calibration_code, Gage.gage_code, CalibrationActivity.activity_type,
                CalibrationActivity.performed_date, CalibrationActivity.result,
                CalibrationActivity.as_found_in_tolerance, CalibrationActivity.as_left_in_tolerance,
                CalibrationActivity.provider_name, tech.c.full_name.label("technician"),
                rev.c.full_name.label("reviewer"), appr.c.full_name.label("approver"),
                CalibrationActivity.released_at, CalibrationActivity.due_date)
         .join(Gage, Gage.id == CalibrationActivity.gage_id)
         .outerjoin(tech, tech.c.id == CalibrationActivity.technician_id)
         .outerjoin(rev, rev.c.id == CalibrationActivity.reviewer_id)
         .outerjoin(appr, appr.c.id == CalibrationActivity.approver_id).where(_released(ctx, p)))
    if p.gage_id:
        q = q.where(CalibrationActivity.gage_id == p.gage_id)
    return _rows(ctx.db.execute(q.order_by(CalibrationActivity.performed_date, CalibrationActivity.calibration_code)))


def as_found_as_left(ctx, p):
    q = (select(CalibrationActivity.calibration_code, Gage.gage_code, CalibrationActivity.performed_date,
                CalibrationPoint.phase, CalibrationPoint.sequence, CalibrationPoint.description,
                CalibrationPoint.nominal, CalibrationPoint.lower_limit, CalibrationPoint.upper_limit,
                CalibrationPoint.measured, CalibrationPoint.unit, CalibrationPoint.in_tolerance)
         .join(CalibrationActivity, CalibrationActivity.id == CalibrationPoint.calibration_id)
         .join(Gage, Gage.id == CalibrationActivity.gage_id)
         .where(_released(ctx, p), CalibrationPoint.superseded.is_(False)))
    if p.gage_id:
        q = q.where(CalibrationActivity.gage_id == p.gage_id)
    return _rows(ctx.db.execute(q.order_by(CalibrationActivity.calibration_code, CalibrationPoint.phase.desc(),
                                           CalibrationPoint.sequence)))


def certificates(ctx, p):
    d_from, d_to, *_ = _period(p, ctx)
    q = (select(CalibrationCertificate.certificate_number, CalibrationCertificate.issuer,
                CalibrationCertificate.issue_date, CalibrationCertificate.status, Gage.gage_code,
                CalibrationActivity.calibration_code)
         .join(Gage, Gage.id == CalibrationCertificate.gage_id)
         .join(CalibrationActivity, CalibrationActivity.id == CalibrationCertificate.calibration_id)
         .where(CalibrationCertificate.organization_id == ctx.organization_id, _plant_scope(ctx, p, Gage.plant_id),
                CalibrationCertificate.issue_date >= d_from, CalibrationCertificate.issue_date <= d_to))
    return _rows(ctx.db.execute(q.order_by(CalibrationCertificate.issue_date.desc())))


def standards_validity(ctx, p):
    today = ctx.today()
    q = (select(Standard.standard_code, Standard.description, Standard.category, Plant.code.label("plant"),
                Standard.serial_number, Standard.last_calibration_date, Standard.valid_until, Standard.control_status)
         .join(Plant, Plant.id == Standard.plant_id)
         .where(Standard.organization_id == ctx.organization_id, _plant_scope(ctx, p, Standard.plant_id)))
    rows = _rows(ctx.db.execute(q.order_by(Standard.valid_until.nulls_first(), Standard.standard_code)))
    for r in rows:
        vu = r["valid_until"]
        r["days_to_expiry"] = (date.fromisoformat(vu) - today).days if vu else None
    return rows


def standards_history(ctx, p):
    q = (select(Standard.standard_code, StandardCertificate.certificate_number, StandardCertificate.issuer,
                StandardCertificate.accreditation, StandardCertificate.calibration_date, StandardCertificate.valid_until,
                StandardCertificate.uncertainty, StandardCertificate.traceability, StandardCertificate.status)
         .join(Standard, Standard.id == StandardCertificate.standard_id)
         .where(StandardCertificate.organization_id == ctx.organization_id, _plant_scope(ctx, p, Standard.plant_id)))
    return _rows(ctx.db.execute(q.order_by(Standard.standard_code, StandardCertificate.calibration_date.desc())))


# ---------------------------------------------------------------- MSA

def msa_studies(ctx, p):
    d_from, d_to, *_ = _period(p, ctx)
    latest = select(MsaRun.study_id, func.max(MsaRun.run_number).label("n")).group_by(MsaRun.study_id).subquery()
    run = MsaRun.__table__.alias()
    q = (select(MsaStudy.study_code, MsaStudy.title, MsaStudy.method, MsaStudy.characteristic, MsaStudy.part_number,
                Gage.gage_code, MsaStudy.status, run.c.run_number, run.c.algorithm_version, run.c.engine_version,
                run.c.decision.label("computed_decision"), MsaStudy.final_decision, MsaStudy.start_date,
                MsaStudy.end_date)
         .join(Gage, Gage.id == MsaStudy.gage_id)
         .outerjoin(latest, latest.c.study_id == MsaStudy.id)
         .outerjoin(run, and_(run.c.study_id == MsaStudy.id, run.c.run_number == latest.c.n))
         .where(MsaStudy.organization_id == ctx.organization_id, _plant_scope(ctx, p, MsaStudy.plant_id),
                MsaStudy.start_date >= d_from, MsaStudy.start_date <= d_to))
    if p.status:
        q = q.where(MsaStudy.status == p.status)
    return _rows(ctx.db.execute(q.order_by(MsaStudy.start_date, MsaStudy.study_code)))


# ---------------------------------------------------------------- laboratory

def lab_requests(ctx, p):
    _, _, s, e = _period(p, ctx)
    req = _users()
    q = (select(ServiceRequest.request_code, ServiceRequest.created_at, LabService.name.label("service"),
                ServiceRequest.customer_type, ServiceRequest.customer_name, ServiceRequest.part_number,
                ServiceRequest.quantity, ServiceRequest.priority, ServiceRequest.requested_date,
                ServiceRequest.committed_date, ServiceRequest.status, req.c.full_name.label("requester"))
         .join(LabService, LabService.id == ServiceRequest.service_id)
         .outerjoin(req, req.c.id == ServiceRequest.requester_id)
         .where(ServiceRequest.organization_id == ctx.organization_id, _plant_scope(ctx, p, ServiceRequest.plant_id),
                ServiceRequest.created_at >= s, ServiceRequest.created_at < e))
    if p.status:
        q = q.where(ServiceRequest.status == p.status)
    return _rows(ctx.db.execute(q.order_by(ServiceRequest.created_at)))


def lab_work_orders(ctx, p):
    _, _, s, e = _period(p, ctx)
    tech = _users()
    q = (select(WorkOrder.work_order_code, ServiceRequest.request_code, LabService.name.label("service"),
                WorkOrder.priority, WorkOrder.status, tech.c.full_name.label("technician"), WorkOrder.planned_hours,
                WorkOrder.scheduled_start, WorkOrder.started_at, WorkOrder.completed_at, WorkOrder.due_date)
         .join(ServiceRequest, ServiceRequest.id == WorkOrder.service_request_id)
         .join(LabService, LabService.id == WorkOrder.service_id).outerjoin(tech, tech.c.id == WorkOrder.technician_id)
         .where(WorkOrder.organization_id == ctx.organization_id, _plant_scope(ctx, p, WorkOrder.plant_id),
                WorkOrder.created_at >= s, WorkOrder.created_at < e))
    if p.status:
        q = q.where(WorkOrder.status == p.status)
    rows = _rows(ctx.db.execute(q.order_by(WorkOrder.created_at)))
    today = ctx.today().isoformat()
    for r in rows:
        r["overdue"] = bool(r["due_date"] and r["status"] not in ("COMPLETED", "CANCELLED") and r["due_date"] < today)
    return rows


def lab_inspections(ctx, p):
    _, _, s, e = _period(p, ctx)
    tech = _users()
    q = (select(WorkOrder.work_order_code, InspectionResult.part_number, InspectionResult.drawing_revision,
                InspectionResult.sample_id, InspectionResult.characteristic_number, InspectionResult.characteristic,
                InspectionResult.nominal, InspectionResult.lower_limit, InspectionResult.upper_limit,
                InspectionResult.measured, InspectionResult.unit, InspectionResult.result, Gage.gage_code,
                InspectionResult.gage_status, tech.c.full_name.label("technician"), InspectionResult.measured_at)
         .join(WorkOrder, WorkOrder.id == InspectionResult.work_order_id)
         .join(Gage, Gage.id == InspectionResult.gage_id).outerjoin(tech, tech.c.id == InspectionResult.technician_id)
         .where(InspectionResult.organization_id == ctx.organization_id, _plant_scope(ctx, p, WorkOrder.plant_id),
                InspectionResult.superseded.is_(False), InspectionResult.measured_at >= s,
                InspectionResult.measured_at < e))
    if p.gage_id:
        q = q.where(InspectionResult.gage_id == p.gage_id)
    return _rows(ctx.db.execute(q.order_by(InspectionResult.measured_at)))


def lab_reports(ctx, p):
    _, _, s, e = _period(p, ctx)
    rev = _users()
    q = (select(MeasurementReport.report_code, MeasurementReport.revision, WorkOrder.work_order_code,
                MeasurementReport.acceptance, MeasurementReport.status, rev.c.full_name.label("reviewer"),
                MeasurementReport.issued_at)
         .join(WorkOrder, WorkOrder.id == MeasurementReport.work_order_id)
         .outerjoin(rev, rev.c.id == MeasurementReport.reviewer_id)
         .where(MeasurementReport.organization_id == ctx.organization_id, _plant_scope(ctx, p, WorkOrder.plant_id),
                MeasurementReport.issued_at >= s, MeasurementReport.issued_at < e))
    return _rows(ctx.db.execute(q.order_by(MeasurementReport.issued_at)))


def lab_turnaround(ctx, p):
    _, _, s, e = _period(p, ctx)
    q = (select(ServiceRequest.request_code, WorkOrder.work_order_code, ServiceRequest.priority,
                ServiceRequest.created_at, WorkOrder.completed_at, ServiceRequest.committed_date)
         .join(WorkOrder, WorkOrder.service_request_id == ServiceRequest.id)
         .where(ServiceRequest.organization_id == ctx.organization_id, _plant_scope(ctx, p, ServiceRequest.plant_id),
                WorkOrder.status == "COMPLETED", WorkOrder.completed_at >= s, WorkOrder.completed_at < e))
    rows = []
    for r in ctx.db.execute(q.order_by(WorkOrder.completed_at)):
        days = (r.completed_at - r.created_at).total_seconds() / 86400
        on_time = None if r.committed_date is None else r.completed_at.date() <= r.committed_date
        rows.append({"request_code": r.request_code, "work_order_code": r.work_order_code, "priority": r.priority,
                     "created_at": plain(r.created_at), "completed_at": plain(r.completed_at),
                     "turnaround_days": round(days, 2), "committed_date": plain(r.committed_date), "on_time": on_time})
    return rows


def lab_capacity(ctx, p):
    d_from, d_to, s, e = _period(p, ctx)
    settings = ctx.db.get(LabSettings, ctx.organization_id)
    hours_day = float(settings.hours_per_technician_day) if settings else 8.0
    work_days = settings.working_days if settings else [1, 2, 3, 4, 5]
    n_days = sum(1 for i in range((d_to - d_from).days + 1) if (d_from + timedelta(days=i)).isoweekday() in work_days)
    tech = _users()
    q = (select(tech.c.full_name.label("technician"), func.count(WorkOrder.id).label("work_orders"),
                func.coalesce(func.sum(WorkOrder.planned_hours), 0).label("planned_hours"))
         .join(tech, tech.c.id == WorkOrder.technician_id)
         .where(WorkOrder.organization_id == ctx.organization_id, _plant_scope(ctx, p, WorkOrder.plant_id),
                WorkOrder.status != "CANCELLED", WorkOrder.scheduled_start >= s, WorkOrder.scheduled_start < e)
         .group_by(tech.c.full_name).order_by(tech.c.full_name))
    rows = _rows(ctx.db.execute(q))
    for r in rows:
        capacity = n_days * hours_day
        r["capacity_hours"] = capacity
        r["utilization_pct"] = round(100.0 * float(r["planned_hours"]) / capacity, 1) if capacity else None
    return rows


# ---------------------------------------------------------------- OOT

def _oot_scope(ctx, p):
    d_from, d_to, *_ = _period(p, ctx)
    return and_(OotCase.organization_id == ctx.organization_id, _plant_scope(ctx, p, OotCase.plant_id),
                OotCase.detected_on >= d_from, OotCase.detected_on <= d_to)


def oot_cases(ctx, p):
    q = (select(OotCase.case_code, Gage.gage_code, OotCase.detection_source, OotCase.detected_on, OotCase.status,
                OotCase.max_deviation, OotCase.restriction_applied, OotCase.gage_released_at, OotCase.risk_level,
                OotCase.impact_start, OotCase.impact_end, OotCase.closed_at)
         .join(Gage, Gage.id == OotCase.gage_id).where(_oot_scope(ctx, p)))
    if p.status == "OPEN":
        q = q.where(OotCase.status.not_in(("CLOSED", "CANCELLED")))
    elif p.status:
        q = q.where(OotCase.status == p.status)
    return _rows(ctx.db.execute(q.order_by(OotCase.detected_on, OotCase.case_code)))


def oot_affected_gages(ctx, p):
    q = (select(Gage.gage_code, Gage.description, func.count(OotCase.id).label("cases"),
                func.count(OotCase.id).filter(OotCase.status.not_in(("CLOSED", "CANCELLED"))).label("open_cases"),
                func.max(OotCase.detected_on).label("last_detected"), Gage.control_status)
         .join(Gage, Gage.id == OotCase.gage_id).where(_oot_scope(ctx, p))
         .group_by(Gage.gage_code, Gage.description, Gage.control_status))
    return _rows(ctx.db.execute(q.order_by(Gage.gage_code)))


def oot_investigations(ctx, p):
    q = (select(OotCase.case_code, Gage.gage_code, OotCase.status, OotCase.risk_level, OotCase.risk_assessment,
                OotCase.investigation_scope, OotCase.containment, OotCase.disposition, OotCase.corrective_actions,
                OotCase.customer_notification_required, OotCase.customer_notified_on)
         .join(Gage, Gage.id == OotCase.gage_id).where(_oot_scope(ctx, p)))
    return _rows(ctx.db.execute(q.order_by(OotCase.case_code)))


def oot_impact(ctx, p):
    q = (select(OotCase.case_code, OotImpactItem.item_type, OotImpactItem.ref_code, OotImpactItem.description,
                OotImpactItem.occurred_at, OotImpactItem.assessment, OotImpactItem.assessment_note)
         .join(OotCase, OotCase.id == OotImpactItem.case_id).where(_oot_scope(ctx, p)))
    return _rows(ctx.db.execute(q.order_by(OotCase.case_code, OotImpactItem.item_type)))


def oot_actions(ctx, p):
    owner = _users()
    q = (select(OotCase.case_code, OotAction.action_type, OotAction.description, owner.c.full_name.label("owner"),
                OotAction.due_date, OotAction.status, OotAction.result_note, OotAction.completed_at)
         .join(OotCase, OotCase.id == OotAction.case_id).outerjoin(owner, owner.c.id == OotAction.owner_id)
         .where(_oot_scope(ctx, p)))
    return _rows(ctx.db.execute(q.order_by(OotCase.case_code, OotAction.created_at)))


def oot_closures(ctx, p):
    q = (select(OotCase.case_code, Gage.gage_code, OotCase.detected_on, OotCase.closed_at, OotCase.risk_level,
                OotCase.disposition, OotCase.gage_released_at, OotCase.gage_release_reason)
         .join(Gage, Gage.id == OotCase.gage_id).where(_oot_scope(ctx, p), OotCase.status == "CLOSED"))
    rows = _rows(ctx.db.execute(q.order_by(OotCase.closed_at)))
    for r in rows:
        if r["closed_at"]:
            r["days_to_close"] = (datetime.fromisoformat(r["closed_at"]).date() - date.fromisoformat(r["detected_on"])).days
    return rows


GAGE = [C("gage_code", "Instrumento", "Gage"), C("description", "Descripción", "Description")]
REPORTS: dict[str, Report] = {r.key: r for r in [
    Report("gage_inventory", "METROLOGY", "Inventario de instrumentos", "Gage inventory", P.GAGES_READ,
           GAGE + [C("type", "Tipo", "Type"), C("plant", "Planta", "Plant"), C("location", "Ubicación", "Location"),
                   C("serial_number", "Serie", "Serial"), C("criticality", "Criticidad", "Criticality"),
                   C("responsible", "Responsable", "Responsible"), C("frequency_days", "Frecuencia (d)", "Frequency (d)"),
                   C("last_calibration_date", "Última calibración", "Last calibration"),
                   C("next_due_date", "Vencimiento", "Due date"), C("status", "Estado", "Status")], gage_inventory),
    Report("gage_history", "METROLOGY", "Historial del instrumento", "Gage history", P.GAGES_READ,
           [C("date", "Fecha", "Date"), C("event", "Evento", "Event"), C("detail", "Detalle", "Detail"),
            C("reason", "Motivo", "Reason")], gage_history, needs_gage=True),
    Report("calibration_program", "METROLOGY", "Programa de calibración", "Calibration program", P.CALIBRATION_READ,
           [C("gage_code", "Instrumento", "Gage"), C("description", "Descripción", "Description"),
            C("plant", "Planta", "Plant"), C("next_due_date", "Vencimiento", "Due date"), C("status", "Estado", "Status"),
            C("calibration_code", "Actividad", "Activity"), C("planned_date", "Planeada", "Planned"),
            C("scheduled_date", "Programada", "Scheduled"), C("activity_status", "Estado actividad", "Activity status")],
           calibration_program, uses_period=True),
    Report("calibrations_overdue", "METROLOGY", "Calibraciones vencidas", "Overdue calibrations", P.CALIBRATION_READ,
           GAGE + [C("plant", "Planta", "Plant"), C("responsible", "Responsable", "Responsible"),
                   C("next_due_date", "Vencimiento", "Due date"), C("days_overdue", "Días vencido", "Days overdue")],
           calibrations_overdue),
    Report("calibrations_performed", "METROLOGY", "Calibraciones realizadas", "Calibrations performed",
           P.CALIBRATION_READ,
           [C("calibration_code", "Actividad", "Activity"), C("gage_code", "Instrumento", "Gage"),
            C("activity_type", "Tipo", "Type"), C("performed_date", "Fecha", "Date"), C("result", "Resultado", "Result"),
            C("as_found_in_tolerance", "As Found OK"), C("as_left_in_tolerance", "As Left OK"),
            C("provider_name", "Proveedor", "Provider"), C("technician", "Técnico", "Technician"),
            C("reviewer", "Revisó", "Reviewer"), C("approver", "Aprobó", "Approver"),
            C("due_date", "Próximo vencimiento", "Next due")], calibrations_performed, uses_period=True),
    Report("as_found_as_left", "METROLOGY", "Resultados As Found / As Left", "As Found / As Left results",
           P.CALIBRATION_READ,
           [C("calibration_code", "Actividad", "Activity"), C("gage_code", "Instrumento", "Gage"),
            C("performed_date", "Fecha", "Date"), C("phase", "Fase", "Phase"), C("sequence", "#"),
            C("nominal", "Nominal"), C("lower_limit", "Límite inf.", "Lower"), C("upper_limit", "Límite sup.", "Upper"),
            C("measured", "Medido", "Measured"), C("unit", "Unidad", "Unit"), C("in_tolerance", "En tolerancia", "In tol.")],
           as_found_as_left, uses_period=True),
    Report("certificates", "METROLOGY", "Certificados de calibración", "Calibration certificates", P.CALIBRATION_READ,
           [C("certificate_number", "Certificado", "Certificate"), C("issuer", "Emisor", "Issuer"),
            C("issue_date", "Emisión", "Issued"), C("gage_code", "Instrumento", "Gage"),
            C("calibration_code", "Actividad", "Activity"), C("status", "Estado", "Status")], certificates,
           uses_period=True),
    Report("standards_validity", "METROLOGY", "Vigencia de patrones", "Standards validity", P.STANDARDS_READ,
           [C("standard_code", "Patrón", "Standard"), C("description", "Descripción", "Description"),
            C("category", "Categoría", "Category"), C("plant", "Planta", "Plant"), C("serial_number", "Serie", "Serial"),
            C("last_calibration_date", "Última calibración", "Last calibration"),
            C("valid_until", "Vigente hasta", "Valid until"), C("days_to_expiry", "Días", "Days"),
            C("control_status", "Estado", "Status")], standards_validity),
    Report("standards_history", "METROLOGY", "Historial de patrones", "Standards history", P.STANDARDS_READ,
           [C("standard_code", "Patrón", "Standard"), C("certificate_number", "Certificado", "Certificate"),
            C("issuer", "Emisor", "Issuer"), C("accreditation", "Acreditación", "Accreditation"),
            C("calibration_date", "Calibración", "Calibrated"), C("valid_until", "Vigente hasta", "Valid until"),
            C("uncertainty", "Incertidumbre", "Uncertainty"), C("traceability", "Trazabilidad", "Traceability"),
            C("status", "Estado", "Status")], standards_history),
    Report("msa_studies", "MSA", "Estudios MSA", "MSA studies", P.MSA_READ,
           [C("study_code", "Estudio", "Study"), C("title", "Título", "Title"), C("method", "Método", "Method"),
            C("characteristic", "Característica", "Characteristic"), C("gage_code", "Instrumento", "Gage"),
            C("status", "Estado", "Status"), C("run_number", "Cálculo", "Run"),
            C("algorithm_version", "Algoritmo", "Algorithm"), C("computed_decision", "Decisión calculada", "Computed"),
            C("final_decision", "Conclusión", "Conclusion"), C("start_date", "Inicio", "Start")], msa_studies,
           uses_period=True),
    Report("lab_requests", "LAB", "Solicitudes de laboratorio", "Laboratory requests", P.LAB_READ,
           [C("request_code", "Solicitud", "Request"), C("created_at", "Creada", "Created"),
            C("service", "Servicio", "Service"), C("customer_name", "Cliente", "Customer"),
            C("part_number", "Parte", "Part"), C("quantity", "Cant.", "Qty"), C("priority", "Prioridad", "Priority"),
            C("requested_date", "Requerida", "Requested"), C("committed_date", "Comprometida", "Committed"),
            C("status", "Estado", "Status"), C("requester", "Solicitante", "Requester")], lab_requests,
           uses_period=True),
    Report("lab_work_orders", "LAB", "Órdenes de trabajo", "Work orders", P.LAB_READ,
           [C("work_order_code", "OT", "WO"), C("request_code", "Solicitud", "Request"),
            C("service", "Servicio", "Service"), C("priority", "Prioridad", "Priority"), C("status", "Estado", "Status"),
            C("technician", "Técnico", "Technician"), C("planned_hours", "Horas plan", "Planned h"),
            C("completed_at", "Terminada", "Completed"), C("due_date", "Compromiso", "Due"),
            C("overdue", "Atrasada", "Overdue")], lab_work_orders, uses_period=True),
    Report("lab_inspections", "LAB", "Inspecciones dimensionales", "Dimensional inspections", P.LAB_READ,
           [C("work_order_code", "OT", "WO"), C("part_number", "Parte", "Part"), C("sample_id", "Muestra", "Sample"),
            C("characteristic_number", "No."), C("characteristic", "Característica", "Characteristic"),
            C("nominal", "Nominal"), C("lower_limit", "Lím. inf.", "Lower"), C("upper_limit", "Lím. sup.", "Upper"),
            C("measured", "Medido", "Measured"), C("unit", "Unidad", "Unit"), C("result", "Resultado", "Result"),
            C("gage_code", "Instrumento", "Gage"), C("measured_at", "Fecha", "Date")], lab_inspections,
           uses_period=True),
    Report("lab_reports", "LAB", "Informes de medición", "Measurement reports", P.LAB_READ,
           [C("report_code", "Informe", "Report"), C("revision", "Rev."), C("work_order_code", "OT", "WO"),
            C("acceptance", "Aceptación", "Acceptance"), C("status", "Estado", "Status"),
            C("reviewer", "Revisó", "Reviewer"), C("issued_at", "Emitido", "Issued")], lab_reports, uses_period=True),
    Report("lab_turnaround", "LAB", "Tiempos de respuesta", "Turnaround times", P.LAB_READ,
           [C("request_code", "Solicitud", "Request"), C("work_order_code", "OT", "WO"),
            C("priority", "Prioridad", "Priority"), C("created_at", "Recibida", "Received"),
            C("completed_at", "Terminada", "Completed"), C("turnaround_days", "Días", "Days"),
            C("committed_date", "Comprometida", "Committed"), C("on_time", "A tiempo", "On time")], lab_turnaround,
           uses_period=True),
    Report("lab_capacity", "LAB", "Capacidad del laboratorio", "Laboratory capacity", P.LAB_READ,
           [C("technician", "Técnico", "Technician"), C("work_orders", "OT", "WOs"),
            C("planned_hours", "Horas planeadas", "Planned hours"), C("capacity_hours", "Capacidad (h)", "Capacity (h)"),
            C("utilization_pct", "Utilización %", "Utilization %")], lab_capacity, uses_period=True),
    Report("oot_cases", "OOT", "Eventos OOT", "OOT events", P.OOT_READ,
           [C("case_code", "Caso", "Case"), C("gage_code", "Instrumento", "Gage"), C("detection_source", "Origen", "Source"),
            C("detected_on", "Detectado", "Detected"), C("status", "Estado", "Status"),
            C("max_deviation", "Desviación", "Deviation"), C("risk_level", "Riesgo", "Risk"),
            C("impact_start", "Impacto desde", "Impact from"), C("impact_end", "Impacto hasta", "Impact to"),
            C("closed_at", "Cerrado", "Closed")], oot_cases, uses_period=True),
    Report("oot_affected_gages", "OOT", "Instrumentos afectados", "Affected gages", P.OOT_READ,
           GAGE + [C("cases", "Casos", "Cases"), C("open_cases", "Abiertos", "Open"),
                   C("last_detected", "Última detección", "Last detected"), C("control_status", "Estado", "Status")],
           oot_affected_gages, uses_period=True),
    Report("oot_investigations", "OOT", "Investigaciones OOT", "OOT investigations", P.OOT_READ,
           [C("case_code", "Caso", "Case"), C("gage_code", "Instrumento", "Gage"), C("status", "Estado", "Status"),
            C("risk_level", "Riesgo", "Risk"), C("risk_assessment", "Evaluación del riesgo", "Risk assessment"),
            C("containment", "Contención", "Containment"), C("disposition", "Disposición", "Disposition"),
            C("customer_notification_required", "Notificar cliente", "Notify customer")], oot_investigations,
           uses_period=True),
    Report("oot_impact", "OOT", "Evaluaciones de impacto", "Impact evaluations", P.OOT_READ,
           [C("case_code", "Caso", "Case"), C("item_type", "Tipo", "Type"), C("ref_code", "Referencia", "Reference"),
            C("description", "Descripción", "Description"), C("assessment", "Evaluación", "Assessment"),
            C("assessment_note", "Nota", "Note")], oot_impact, uses_period=True),
    Report("oot_actions", "OOT", "Acciones OOT", "OOT actions", P.OOT_READ,
           [C("case_code", "Caso", "Case"), C("action_type", "Tipo", "Type"), C("description", "Descripción", "Description"),
            C("owner", "Responsable", "Owner"), C("due_date", "Compromiso", "Due"), C("status", "Estado", "Status"),
            C("result_note", "Resultado", "Result")], oot_actions, uses_period=True),
    Report("oot_closures", "OOT", "Cierres OOT", "OOT closures", P.OOT_READ,
           [C("case_code", "Caso", "Case"), C("gage_code", "Instrumento", "Gage"), C("detected_on", "Detectado", "Detected"),
            C("closed_at", "Cerrado", "Closed"), C("days_to_close", "Días", "Days"), C("risk_level", "Riesgo", "Risk"),
            C("disposition", "Disposición", "Disposition")], oot_closures, uses_period=True),
]}
