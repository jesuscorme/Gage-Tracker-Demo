"""Executive / operational dashboard.

Every figure is computed live from the operational tables with the same filter
(``Filters``) applied to the gage population, so totals reconcile with each other and
with the source lists: by-status, by-type and by-plant breakdowns all partition the
same filtered gage set. Sections the user has no permission for are omitted (None).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import and_, func, or_, select, true

from app.modules.calibration.models import CalibrationActivity
from app.modules.competency.models import Authorization, CompetencyRecord
from app.modules.gages import service as gages
from app.modules.gages.models import Gage, GageType
from app.modules.gages.status import GageStatus
from app.modules.identity.deps import TenantContext
from app.modules.identity.models import User
from app.modules.identity.permissions import P
from app.modules.laboratory.models import ServiceRequest, WorkOrder
from app.modules.msa.models import MsaRun, MsaStudy
from app.modules.oot.models import OotCase
from app.modules.organizations.models import Plant
from app.modules.standards.models import Standard

CAL_PENDING = ("PLANNED", "REQUESTED", "SCHEDULED")
CAL_IN_PROCESS = ("IN_PROGRESS", "PENDING_REVIEW", "PENDING_APPROVAL", "APPROVED")
REQ_OPEN = ("SUBMITTED", "APPROVED", "IN_PROGRESS")
WO_OPEN = ("PENDING", "SCHEDULED", "IN_PROGRESS")
OOT_CLOSED = ("CLOSED", "CANCELLED")
MSA_DONE = ("APPROVED", "CANCELLED")


@dataclass
class Filters:
    plant_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    gage_type_id: uuid.UUID | None = None
    status: str | None = None
    responsible_id: uuid.UUID | None = None
    date_from: date | None = None
    date_to: date | None = None


def _months(d1: date, d2: date) -> list[str]:
    out, y, m = [], d1.year, d1.month
    while (y, m) <= (d2.year, d2.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _series(rows, months) -> list[dict]:
    got = {k: n for k, n in rows if k}
    return [{"month": m, "count": got.get(m, 0)} for m in months]


def overview(ctx: TenantContext, f: Filters) -> dict:
    db, org, today = ctx.db, ctx.organization_id, ctx.today()
    d_to = f.date_to or today
    d_from = f.date_from or (d_to.replace(day=1) - timedelta(days=150)).replace(day=1)
    months = _months(d_from, d_to)
    start_dt = datetime.combine(d_from, time.min, tzinfo=UTC)
    end_dt = datetime.combine(d_to + timedelta(days=1), time.min, tzinfo=UTC)
    status = gages._status_sql(ctx)
    soon = today + timedelta(days=ctx.organization.due_soon_days)

    # Filtered gage population (tenant + plant scope + filters).
    g = gages.scoped_query(ctx).with_only_columns(Gage.id)
    if f.plant_id:
        g = g.where(Gage.plant_id == f.plant_id)
    if f.department_id:
        g = g.where(Gage.department_id == f.department_id)
    if f.gage_type_id:
        g = g.where(Gage.gage_type_id == f.gage_type_id)
    if f.responsible_id:
        g = g.where(Gage.responsible_user_id == f.responsible_id)
    if f.status:
        g = g.where(status == f.status)
    gage_ids = g.subquery()
    in_pop = Gage.id.in_(select(gage_ids.c.id))
    plant_ok = (lambda col: col.in_(ctx.plant_ids)) if ctx.plant_ids is not None else (lambda col: true())  # noqa: E731
    plant_filter = (lambda col: col == f.plant_id) if f.plant_id else (lambda col: true())  # noqa: E731

    out: dict = {"as_of": today, "period": {"from": d_from, "to": d_to, "months": months},
                 "due_soon_days": ctx.organization.due_soon_days, "filters": {k: v for k, v in f.__dict__.items() if v}}

    # ---------------------------------------------------------------- gages
    by_status = {s.value: 0 for s in GageStatus}
    by_status.update(dict(db.execute(select(status, func.count()).where(in_pop).group_by(status)).all()))
    total = sum(by_status.values())
    by_type = [{"type": code, "name": name, "count": n} for code, name, n in db.execute(
        select(GageType.code, GageType.name, func.count(Gage.id)).join(GageType, GageType.id == Gage.gage_type_id)
        .where(in_pop).group_by(GageType.code, GageType.name).order_by(func.count(Gage.id).desc()))]
    compliance = []
    for code, name, n_total, n_ok, n_overdue in db.execute(
            select(Plant.code, Plant.name, func.count(Gage.id),
                   func.count(Gage.id).filter(status.in_(("CALIBRATED", "DUE_SOON"))),
                   func.count(Gage.id).filter(status == "OVERDUE"))
            .join(Plant, Plant.id == Gage.plant_id).where(in_pop, status != "INACTIVE")
            .group_by(Plant.code, Plant.name).order_by(Plant.code)):
        compliance.append({"plant": code, "name": name, "active": n_total, "current": n_ok, "overdue": n_overdue,
                           "pct_current": round(100.0 * n_ok / n_total, 1) if n_total else None})
    upcoming = [{"id": i, "gage_code": c, "description": d, "next_due_date": nd, "status": s} for i, c, d, nd, s in db.execute(
        select(Gage.id, Gage.gage_code, Gage.description, Gage.next_due_date, status).where(
            in_pop, status.in_(("DUE_SOON", "OVERDUE"))).order_by(Gage.next_due_date).limit(15))]
    out["gages"] = {
        "total": total, "active": total - by_status["INACTIVE"],
        "current": by_status["CALIBRATED"] + by_status["DUE_SOON"], "calibrated": by_status["CALIBRATED"],
        "due_soon": by_status["DUE_SOON"], "overdue": by_status["OVERDUE"],
        "out_of_service": by_status["OUT_OF_SERVICE"], "in_calibration": by_status["IN_CALIBRATION"],
        "by_status": by_status, "by_type": by_type, "compliance_by_plant": compliance, "upcoming": upcoming,
    }

    # ---------------------------------------------------------------- calibration
    if ctx.has(P.CALIBRATION_READ):
        counts = dict(db.execute(select(CalibrationActivity.status, func.count()).where(
            CalibrationActivity.organization_id == org, CalibrationActivity.gage_id.in_(select(gage_ids.c.id)))
            .group_by(CalibrationActivity.status)).all())
        month = func.to_char(CalibrationActivity.performed_date, "YYYY-MM")
        released = db.execute(select(month, func.count()).where(
            CalibrationActivity.organization_id == org, CalibrationActivity.gage_id.in_(select(gage_ids.c.id)),
            CalibrationActivity.status == "RELEASED", CalibrationActivity.performed_date >= d_from,
            CalibrationActivity.performed_date <= d_to).group_by(month)).all()
        results = dict(db.execute(select(CalibrationActivity.result, func.count()).where(
            CalibrationActivity.organization_id == org, CalibrationActivity.gage_id.in_(select(gage_ids.c.id)),
            CalibrationActivity.status == "RELEASED", CalibrationActivity.performed_date >= d_from,
            CalibrationActivity.performed_date <= d_to).group_by(CalibrationActivity.result)).all())
        series = _series(released, months)
        out["calibration"] = {
            "pending": sum(counts.get(s, 0) for s in CAL_PENDING),
            "in_process": sum(counts.get(s, 0) for s in CAL_IN_PROCESS),
            "by_status": counts, "released_in_period": sum(p["count"] for p in series),
            "released_by_month": series, "results_in_period": {k or "—": v for k, v in results.items()},
        }
    else:
        out["calibration"] = None

    # ---------------------------------------------------------------- laboratory
    if ctx.has(P.LAB_READ):
        req_scope = and_(ServiceRequest.organization_id == org, plant_ok(ServiceRequest.plant_id),
                         plant_filter(ServiceRequest.plant_id))
        wo_scope = and_(WorkOrder.organization_id == org, plant_ok(WorkOrder.plant_id), plant_filter(WorkOrder.plant_id))
        req_counts = dict(db.execute(select(ServiceRequest.status, func.count()).where(req_scope)
                                     .group_by(ServiceRequest.status)).all())
        wo_counts = dict(db.execute(select(WorkOrder.status, func.count()).where(wo_scope)
                                    .group_by(WorkOrder.status)).all())
        overdue = db.scalar(select(func.count()).where(wo_scope, WorkOrder.status.in_(WO_OPEN),
                                                       WorkOrder.due_date < today)) or 0
        load = [{"technician": name or "—", "open_orders": n, "planned_hours": float(h or 0)} for name, n, h in db.execute(
            select(User.full_name, func.count(WorkOrder.id), func.sum(WorkOrder.planned_hours))
            .outerjoin(User, User.id == WorkOrder.technician_id).where(wo_scope, WorkOrder.status.in_(WO_OPEN))
            .group_by(User.full_name).order_by(func.sum(WorkOrder.planned_hours).desc().nulls_last()))]
        cmonth = func.to_char(WorkOrder.completed_at, "YYYY-MM")
        completed = _series(db.execute(select(cmonth, func.count()).where(
            wo_scope, WorkOrder.status == "COMPLETED", WorkOrder.completed_at >= start_dt,
            WorkOrder.completed_at < end_dt).group_by(cmonth)).all(), months)
        rmonth = func.to_char(ServiceRequest.created_at, "YYYY-MM")
        received = _series(db.execute(select(rmonth, func.count()).where(
            req_scope, ServiceRequest.created_at >= start_dt, ServiceRequest.created_at < end_dt)
            .group_by(rmonth)).all(), months)
        out["laboratory"] = {
            "requests_open": sum(req_counts.get(s, 0) for s in REQ_OPEN), "requests_by_status": req_counts,
            "work_orders_open": sum(wo_counts.get(s, 0) for s in WO_OPEN), "work_orders_by_status": wo_counts,
            "work_orders_overdue": overdue, "workload": load, "completed_by_month": completed,
            "requests_by_month": received,
        }
    else:
        out["laboratory"] = None

    # ---------------------------------------------------------------- MSA
    if ctx.has(P.MSA_READ):
        scope = and_(MsaStudy.organization_id == org, MsaStudy.gage_id.in_(select(gage_ids.c.id)))
        latest = (select(MsaRun.study_id, func.max(MsaRun.run_number).label("n")).group_by(MsaRun.study_id).subquery())
        decision = select(MsaRun.decision).join(latest, and_(latest.c.study_id == MsaRun.study_id,
                                                             latest.c.n == MsaRun.run_number)) \
            .where(MsaRun.study_id == MsaStudy.id).scalar_subquery()
        effective = func.coalesce(MsaStudy.final_decision, decision, "NOT_CALCULATED")
        st = dict(db.execute(select(MsaStudy.status, func.count()).where(scope).group_by(MsaStudy.status)).all())
        by_method = {}
        for method, dec, n in db.execute(select(MsaStudy.method, effective, func.count()).where(
                scope, MsaStudy.status != "CANCELLED").group_by(MsaStudy.method, effective)):
            by_method.setdefault(method, {})[dec] = n
        out["msa"] = {
            "open": sum(n for s, n in st.items() if s not in MSA_DONE), "completed": st.get("APPROVED", 0),
            "not_acceptable": sum(m.get("NOT_ACCEPTABLE", 0) for m in by_method.values()),
            "by_status": st, "by_method": by_method,
        }
    else:
        out["msa"] = None

    # ---------------------------------------------------------------- OOT
    if ctx.has(P.OOT_READ):
        scope = and_(OotCase.organization_id == org, OotCase.gage_id.in_(select(gage_ids.c.id)))
        st = dict(db.execute(select(OotCase.status, func.count()).where(scope).group_by(OotCase.status)).all())
        omonth = func.to_char(OotCase.detected_on, "YYYY-MM")
        out["oot"] = {
            "open": sum(n for s, n in st.items() if s not in OOT_CLOSED),
            "gages_restricted": db.scalar(select(func.count(func.distinct(OotCase.gage_id))).where(
                scope, OotCase.restriction_applied.is_(True), OotCase.gage_released_at.is_(None),
                OotCase.status.not_in(OOT_CLOSED))) or 0,
            "by_status": st,
            "detected_by_month": _series(db.execute(select(omonth, func.count()).where(
                scope, OotCase.detected_on >= d_from, OotCase.detected_on <= d_to).group_by(omonth)).all(), months),
        }
    else:
        out["oot"] = None

    # ---------------------------------------------------------------- expirations
    exp = {}
    if ctx.has(P.STANDARDS_READ):
        exp["standards_expiring"] = db.scalar(select(func.count()).where(
            Standard.organization_id == org, plant_ok(Standard.plant_id), plant_filter(Standard.plant_id),
            Standard.control_status != "INACTIVE", Standard.valid_until >= today, Standard.valid_until <= soon)) or 0
        exp["standards_expired"] = db.scalar(select(func.count()).where(
            Standard.organization_id == org, plant_ok(Standard.plant_id), plant_filter(Standard.plant_id),
            Standard.control_status != "INACTIVE",
            or_(Standard.valid_until < today, Standard.valid_until.is_(None)))) or 0
    if ctx.has(P.COMPETENCY_READ):
        exp["authorizations_expiring"] = db.scalar(select(func.count()).where(
            Authorization.organization_id == org, Authorization.revoked_at.is_(None),
            Authorization.valid_until >= today, Authorization.valid_until <= today + timedelta(days=30))) or 0
        exp["competency_records_expiring"] = db.scalar(select(func.count()).where(
            CompetencyRecord.organization_id == org, CompetencyRecord.valid_until >= today,
            CompetencyRecord.valid_until <= today + timedelta(days=30))) or 0
    out["expirations"] = exp or None
    return out
