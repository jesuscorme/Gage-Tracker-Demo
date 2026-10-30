"""Compliance & Audit: an evidence query layer over existing records.

Nothing here stores or copies business data; every figure is computed from the
operational tables at query time. The clause references help organizations locate the
records they may use as evidence. Gage Tracker does not certify organizations nor
guarantee compliance: applicable requirements and their fulfilment are evaluated by
the organization (and its auditors).
"""

import io
import uuid
from datetime import UTC, datetime, timedelta

from openpyxl import Workbook
from sqlalchemy import func, or_, select

from app.core.errors import NotFoundError
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import plain
from app.modules.calibration.models import CalibrationActivity, CalibrationCertificate, CalibrationStandardUsage
from app.modules.competency.models import Authorization, CompetencyRecord
from app.modules.configuration.models import ConfigItem, ConfigVersion, WorkflowEvent
from app.modules.documents.models import Attachment
from app.modules.gages import service as gages
from app.modules.gages.models import Gage, GageMovement, GageStatusHistory
from app.modules.identity.deps import TenantContext
from app.modules.identity.models import User
from app.modules.integrations.models import ImportJob
from app.modules.laboratory.models import LabService, MeasurementReport, WorkOrder
from app.modules.msa.models import MsaCriteriaSet, MsaRun, MsaStudy
from app.modules.oot.models import OotAction, OotCase, OotImpactItem
from app.modules.standards.models import Standard, StandardCertificate

DISCLAIMER = ("Gage Tracker organizes records that the organization may use as evidence. It does not certify the "
              "organization nor guarantee compliance with ISO 9001, IATF 16949 or customer requirements: applicable "
              "requirements and their fulfilment must be evaluated by the organization.")

# Clause references (titles abbreviated). Mapping clause -> processes whose records relate to it.
CLAUSES = [
    {"standard": "ISO 9001:2015", "clause": "7.1.5.1", "title": "Monitoring and measuring resources - general",
     "processes": ["EQUIPMENT_CONTROL", "CALIBRATION"]},
    {"standard": "ISO 9001:2015", "clause": "7.1.5.2", "title": "Measurement traceability",
     "processes": ["CALIBRATION", "TRACEABILITY", "OOT"]},
    {"standard": "ISO 9001:2015", "clause": "7.2", "title": "Competence", "processes": ["COMPETENCE"]},
    {"standard": "ISO 9001:2015", "clause": "7.5.3", "title": "Control of documented information",
     "processes": ["RECORDS", "CONFIGURATION"]},
    {"standard": "IATF 16949:2016", "clause": "7.1.5.1.1", "title": "Measurement systems analysis",
     "processes": ["MSA"]},
    {"standard": "IATF 16949:2016", "clause": "7.1.5.2.1", "title": "Calibration/verification records",
     "processes": ["EQUIPMENT_CONTROL", "CALIBRATION", "OOT"]},
    {"standard": "IATF 16949:2016", "clause": "7.1.5.3.1", "title": "Internal laboratory",
     "processes": ["LABORATORY", "COMPETENCE"]},
    {"standard": "IATF 16949:2016", "clause": "7.1.5.3.2", "title": "External laboratory",
     "processes": ["CALIBRATION"]},
    {"standard": "IATF 16949:2016", "clause": "7.2.1", "title": "Competence - supplemental",
     "processes": ["COMPETENCE"]},
    {"standard": "IATF 16949:2016", "clause": "7.5.3.2.1", "title": "Record retention", "processes": ["RECORDS"]},
]
PROCESSES = {
    "EQUIPMENT_CONTROL": "Control of measuring equipment (inventory, status, due dates)",
    "CALIBRATION": "Calibration and verification (records, review, approval, certificates)",
    "TRACEABILITY": "Metrological traceability (reference standards and their certificates)",
    "OOT": "Out-of-tolerance management (impact on previous results, actions, customer notification)",
    "MSA": "Measurement systems analysis (studies, methods, criteria, decisions)",
    "COMPETENCE": "Competence and authorizations of personnel",
    "LABORATORY": "Laboratory operations (scope of services, work orders, reports)",
    "RECORDS": "Control of records (audit trail, immutable records, retention)",
    "CONFIGURATION": "Controlled changes of configuration (versions and approvals)",
}


def _count(ctx, stmt) -> int:
    return ctx.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0


def _gage_scope(ctx: TenantContext, stmt, plant_col):
    """Restrict to the plants the user may access."""
    return stmt.where(plant_col.in_(ctx.plant_ids)) if ctx.plant_ids is not None else stmt


def process_evidence(ctx: TenantContext, code: str) -> dict:
    """Counts of evidence and gaps for one process (computed live)."""
    org = ctx.organization_id
    today = ctx.today()
    status = gages._status_sql(ctx)
    ev, gaps = {}, {}
    if code == "EQUIPMENT_CONTROL":
        base = _gage_scope(ctx, select(Gage.id).where(Gage.organization_id == org), Gage.plant_id)
        ev["gages"] = _count(ctx, base)
        ev["status_changes_recorded"] = _count(ctx, select(GageStatusHistory.id).join(Gage).where(
            GageStatusHistory.organization_id == org, *([Gage.plant_id.in_(ctx.plant_ids)] if ctx.plant_ids else [])))
        ev["movements_recorded"] = _count(ctx, select(GageMovement.id).where(GageMovement.organization_id == org))
        gaps["overdue_gages"] = _count(ctx, base.where(status == "OVERDUE"))
        gaps["gages_without_calibration_date"] = _count(ctx, base.where(
            Gage.last_calibration_date.is_(None), Gage.control_status != "INACTIVE"))
    elif code == "CALIBRATION":
        base = _gage_scope(ctx, select(CalibrationActivity.id).where(CalibrationActivity.organization_id == org),
                           CalibrationActivity.plant_id)
        ev["released_activities"] = _count(ctx, base.where(CalibrationActivity.status == "RELEASED"))
        ev["certificates"] = _count(ctx, select(CalibrationCertificate.id).where(
            CalibrationCertificate.organization_id == org, CalibrationCertificate.status == "CURRENT"))
        ev["reviewed_and_approved"] = _count(ctx, base.where(CalibrationActivity.approver_id.is_not(None),
                                                             CalibrationActivity.reviewer_id.is_not(None)))
        gaps["awaiting_review_or_approval"] = _count(ctx, base.where(
            CalibrationActivity.status.in_(("PENDING_REVIEW", "PENDING_APPROVAL", "APPROVED"))))
    elif code == "TRACEABILITY":
        base = _gage_scope(ctx, select(Standard.id).where(Standard.organization_id == org,
                                                          Standard.control_status != "INACTIVE"), Standard.plant_id)
        ev["standards"] = _count(ctx, base)
        ev["standard_certificates"] = _count(ctx, select(StandardCertificate.id).where(
            StandardCertificate.organization_id == org))
        ev["standard_usages_in_calibrations"] = _count(ctx, select(CalibrationStandardUsage.id).where(
            CalibrationStandardUsage.organization_id == org))
        gaps["standards_expired"] = _count(ctx, base.where(or_(Standard.valid_until < today,
                                                               Standard.valid_until.is_(None))))
    elif code == "OOT":
        base = _gage_scope(ctx, select(OotCase.id).where(OotCase.organization_id == org), OotCase.plant_id)
        ev["cases"] = _count(ctx, base)
        ev["cases_closed"] = _count(ctx, base.where(OotCase.status == "CLOSED"))
        ev["impact_items_assessed"] = _count(ctx, select(OotImpactItem.id).where(
            OotImpactItem.organization_id == org, OotImpactItem.assessment != "PENDING"))
        ev["actions_completed"] = _count(ctx, select(OotAction.id).where(OotAction.organization_id == org,
                                                                        OotAction.status == "DONE"))
        gaps["open_cases"] = _count(ctx, base.where(OotCase.status.not_in(("CLOSED", "CANCELLED"))))
        gaps["open_cases_without_analysis"] = _count(ctx, base.where(
            OotCase.status.not_in(("CLOSED", "CANCELLED")), OotCase.analysis_generated_at.is_(None)))
    elif code == "MSA":
        base = _gage_scope(ctx, select(MsaStudy.id).where(MsaStudy.organization_id == org), MsaStudy.plant_id)
        ev["studies"] = _count(ctx, base)
        ev["approved_studies"] = _count(ctx, base.where(MsaStudy.status == "APPROVED"))
        ev["calculation_runs"] = _count(ctx, select(MsaRun.id).where(MsaRun.organization_id == org))
        ev["approved_criteria_sets"] = _count(ctx, select(MsaCriteriaSet.id).where(
            MsaCriteriaSet.organization_id == org, MsaCriteriaSet.status == "APPROVED"))
        approved_gages = select(MsaStudy.gage_id).where(MsaStudy.organization_id == org,
                                                        MsaStudy.status == "APPROVED")
        gaps["high_criticality_gages_without_approved_msa"] = _count(ctx, _gage_scope(ctx, select(Gage.id).where(
            Gage.organization_id == org, Gage.criticality == "HIGH", Gage.control_status != "INACTIVE",
            Gage.id.not_in(approved_gages)), Gage.plant_id))
        gaps["studies_in_review"] = _count(ctx, base.where(MsaStudy.status == "IN_REVIEW"))
    elif code == "COMPETENCE":
        current = select(Authorization.id).where(
            Authorization.organization_id == org, Authorization.revoked_at.is_(None),
            Authorization.valid_from <= today, or_(Authorization.valid_until.is_(None),
                                                   Authorization.valid_until >= today))
        ev["current_authorizations"] = _count(ctx, current)
        ev["competency_records"] = _count(ctx, select(CompetencyRecord.id).where(
            CompetencyRecord.organization_id == org))
        gaps["authorizations_expiring_30_days"] = _count(ctx, current.where(
            Authorization.valid_until.is_not(None), Authorization.valid_until <= today + timedelta(days=30)))
    elif code == "LABORATORY":
        ev["services_in_scope"] = _count(ctx, select(LabService.id).where(LabService.organization_id == org,
                                                                         LabService.is_active.is_(True)))
        ev["completed_work_orders"] = _count(ctx, _gage_scope(ctx, select(WorkOrder.id).where(
            WorkOrder.organization_id == org, WorkOrder.status == "COMPLETED"), WorkOrder.plant_id))
        ev["issued_reports"] = _count(ctx, select(MeasurementReport.id).where(
            MeasurementReport.organization_id == org))
        gaps["completed_without_report"] = _count(ctx, _gage_scope(ctx, select(WorkOrder.id).where(
            WorkOrder.organization_id == org, WorkOrder.status == "COMPLETED",
            WorkOrder.id.not_in(select(MeasurementReport.work_order_id))), WorkOrder.plant_id))
    elif code == "RECORDS":
        ev["audit_events"] = _count(ctx, select(AuditEvent.id).where(AuditEvent.organization_id == org))
        ev["locked_documents"] = _count(ctx, select(Attachment.id).where(Attachment.organization_id == org,
                                                                         Attachment.is_locked.is_(True)))
        ev["workflow_events"] = _count(ctx, select(WorkflowEvent.id).where(WorkflowEvent.organization_id == org))
    elif code == "CONFIGURATION":
        ev["configuration_items"] = _count(ctx, select(ConfigItem.id).where(ConfigItem.organization_id == org))
        ev["approved_versions"] = _count(ctx, select(ConfigVersion.id).where(
            ConfigVersion.organization_id == org, ConfigVersion.decided_by.is_not(None),
            ConfigVersion.status.in_(("ACTIVE", "SUPERSEDED"))))
        gaps["drafts_pending_approval"] = _count(ctx, select(ConfigVersion.id).where(
            ConfigVersion.organization_id == org, ConfigVersion.status == "DRAFT"))
    else:
        raise NotFoundError("Unknown process")
    total_ev = sum(ev.values())
    state = "NO_RECORDS" if total_ev == 0 else ("ATTENTION" if any(gaps.values()) else "EVIDENCE_AVAILABLE")
    return {"process": code, "description": PROCESSES[code], "evidence": ev, "gaps": gaps, "state": state,
            "clauses": [f"{c['standard']} {c['clause']}" for c in CLAUSES if code in c["processes"]]}


def matrix(ctx: TenantContext) -> dict:
    procs = {code: process_evidence(ctx, code) for code in PROCESSES}
    clauses = []
    for c in CLAUSES:
        states = [procs[p]["state"] for p in c["processes"]]
        clauses.append(c | {"state": "NO_RECORDS" if all(s == "NO_RECORDS" for s in states)
                            else ("ATTENTION" if "ATTENTION" in states else "EVIDENCE_AVAILABLE")})
    return {"disclaimer": DISCLAIMER, "generated_at": datetime.now(UTC), "processes": list(procs.values()),
            "clauses": clauses}


def clause(ctx: TenantContext, standard: str, number: str) -> dict:
    c = next((c for c in CLAUSES if c["clause"] == number and c["standard"].split(":")[0].replace(" ", "").lower()
              == standard.replace(" ", "").lower()), None)
    if c is None:
        raise NotFoundError("Clause not in the catalogue")
    return c | {"disclaimer": DISCLAIMER, "processes": [process_evidence(ctx, p) for p in c["processes"]]}


# ---------------------------------------------------------------- gage audit dossier

def _user_names(ctx, ids) -> dict:
    ids = {i for i in ids if i}
    return dict(ctx.db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all()) if ids else {}


def dossier(ctx: TenantContext, gage_id: uuid.UUID) -> dict:
    g = gages.get_gage(ctx, gage_id)
    cals = list(ctx.db.scalars(select(CalibrationActivity).where(CalibrationActivity.gage_id == g.id)
                               .order_by(CalibrationActivity.performed_date.desc().nulls_last())))
    certs = list(ctx.db.scalars(select(CalibrationCertificate).where(CalibrationCertificate.gage_id == g.id)
                                .order_by(CalibrationCertificate.issue_date.desc())))
    history = list(ctx.db.scalars(select(GageStatusHistory).where(GageStatusHistory.gage_id == g.id)
                                  .order_by(GageStatusHistory.changed_at)))
    moves = list(ctx.db.scalars(select(GageMovement).where(GageMovement.gage_id == g.id)
                                .order_by(GageMovement.moved_at)))
    cases = list(ctx.db.scalars(select(OotCase).where(OotCase.gage_id == g.id).order_by(OotCase.detected_on)))
    studies = list(ctx.db.scalars(select(MsaStudy).where(MsaStudy.gage_id == g.id).order_by(MsaStudy.start_date)))
    docs = list(ctx.db.scalars(select(Attachment).where(Attachment.entity_type == "gage", Attachment.entity_id == g.id)))
    audit_rows = list(ctx.db.scalars(select(AuditEvent).where(AuditEvent.organization_id == ctx.organization_id,
                                                              AuditEvent.entity_type == "gage",
                                                              AuditEvent.entity_id == str(g.id))
                                     .order_by(AuditEvent.created_at.desc()).limit(500)))
    names = _user_names(ctx, [c.reviewer_id for c in cals] + [c.approver_id for c in cals] +
                        [c.released_by for c in cals] + [c.technician_id for c in cals] +
                        [h.changed_by for h in history] + [a.actor_user_id for a in audit_rows])
    return {
        "disclaimer": DISCLAIMER,
        "gage": {"id": g.id, "gage_code": g.gage_code, "description": g.description, "serial_number": g.serial_number,
                 "status": gages.current_status(ctx, g).value, "criticality": g.criticality,
                 "last_calibration_date": g.last_calibration_date, "next_due_date": g.next_due_date,
                 "calibration_frequency_days": g.calibration_frequency_days},
        "calibrations": [{"calibration_code": c.calibration_code, "activity_type": c.activity_type,
                          "status": c.status, "performed_date": c.performed_date, "result": c.result,
                          "as_found_in_tolerance": c.as_found_in_tolerance,
                          "as_left_in_tolerance": c.as_left_in_tolerance,
                          "technician": names.get(c.technician_id), "reviewer": names.get(c.reviewer_id),
                          "reviewed_at": c.reviewed_at, "approver": names.get(c.approver_id),
                          "approved_at": c.approved_at, "released_by": names.get(c.released_by),
                          "released_at": c.released_at} for c in cals],
        "certificates": [{"certificate_number": c.certificate_number, "issuer": c.issuer, "issue_date": c.issue_date,
                          "status": c.status, "attachment_id": c.attachment_id} for c in certs],
        "status_history": [{"at": h.changed_at, "from": h.from_status, "to": h.to_status, "reason": h.reason,
                            "by": names.get(h.changed_by)} for h in history],
        "movements": [{"at": m.moved_at, "changes": m.changes, "reason": m.reason} for m in moves],
        "oot_cases": [{"case_code": c.case_code, "status": c.status, "detected_on": c.detected_on,
                       "impact_start": c.impact_start, "impact_end": c.impact_end, "risk_level": c.risk_level,
                       "closed_at": c.closed_at} for c in cases],
        "msa_studies": [{"study_code": s.study_code, "method": s.method, "status": s.status,
                         "characteristic": s.characteristic, "final_decision": s.final_decision} for s in studies],
        "documents": [{"id": d.id, "category": d.category, "filename": d.original_filename, "sha256": d.sha256,
                       "locked": d.is_locked, "removed": d.removed_at is not None} for d in docs],
        "audit_trail": [{"at": a.created_at, "action": a.action, "by": names.get(a.actor_user_id),
                         "reason": a.reason} for a in audit_rows],
    }


# ---------------------------------------------------------------- searches and reports

def certificates(ctx: TenantContext, q: str | None, valid_on) -> list[dict]:
    out = []
    stmt = (select(CalibrationCertificate, Gage.gage_code).join(Gage, Gage.id == CalibrationCertificate.gage_id)
            .where(CalibrationCertificate.organization_id == ctx.organization_id))
    stmt = _gage_scope(ctx, stmt, Gage.plant_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(CalibrationCertificate.certificate_number.ilike(like),
                              CalibrationCertificate.issuer.ilike(like), Gage.gage_code.ilike(like)))
    for c, code in ctx.db.execute(stmt.order_by(CalibrationCertificate.issue_date.desc()).limit(200)):
        out.append({"kind": "GAGE_CALIBRATION", "subject": code, "certificate_number": c.certificate_number,
                    "issuer": c.issuer, "issue_date": c.issue_date, "valid_until": None, "status": c.status,
                    "attachment_id": c.attachment_id})
    stmt = (select(StandardCertificate, Standard.standard_code).join(Standard, Standard.id == StandardCertificate.standard_id)
            .where(StandardCertificate.organization_id == ctx.organization_id))
    stmt = _gage_scope(ctx, stmt, Standard.plant_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(StandardCertificate.certificate_number.ilike(like),
                              StandardCertificate.issuer.ilike(like), Standard.standard_code.ilike(like)))
    if valid_on:
        stmt = stmt.where(StandardCertificate.valid_until >= valid_on)
    for c, code in ctx.db.execute(stmt.order_by(StandardCertificate.issue_date.desc()).limit(200)):
        out.append({"kind": "REFERENCE_STANDARD", "subject": code, "certificate_number": c.certificate_number,
                    "issuer": c.issuer, "issue_date": c.issue_date, "valid_until": c.valid_until,
                    "status": c.status, "attachment_id": c.attachment_id})
    return out


def approvals(ctx: TenantContext, since, until) -> list[dict]:
    org = ctx.organization_id
    out = []
    since_dt = datetime.combine(since, datetime.min.time(), tzinfo=UTC)
    until_dt = datetime.combine(until + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    cals = ctx.db.scalars(_gage_scope(ctx, select(CalibrationActivity).where(
        CalibrationActivity.organization_id == org, CalibrationActivity.approved_at >= since_dt,
        CalibrationActivity.approved_at < until_dt), CalibrationActivity.plant_id))
    cals = list(cals)
    names = _user_names(ctx, [c.approver_id for c in cals] + [c.reviewer_id for c in cals])
    for c in cals:
        out.append({"record": c.calibration_code, "type": "calibration", "action": "APPROVE",
                    "by": names.get(c.approver_id), "at": c.approved_at,
                    "detail": f"reviewed by {names.get(c.reviewer_id)}"})
    events = list(ctx.db.scalars(select(WorkflowEvent).where(
        WorkflowEvent.organization_id == org, WorkflowEvent.action.in_(("REVIEW", "APPROVE", "RELEASE")),
        WorkflowEvent.occurred_at >= since_dt, WorkflowEvent.occurred_at < until_dt)))
    names |= _user_names(ctx, [e.actor_id for e in events])
    codes = dict(ctx.db.execute(select(MsaStudy.id, MsaStudy.study_code).where(MsaStudy.organization_id == org)).all())
    codes |= dict(ctx.db.execute(select(OotCase.id, OotCase.case_code).where(OotCase.organization_id == org)).all())
    for e in events:
        out.append({"record": codes.get(e.entity_id, str(e.entity_id)), "type": e.entity_type, "action": e.action,
                    "by": names.get(e.actor_id), "at": e.occurred_at,
                    "detail": f"{e.from_state} -> {e.to_state or '(vote)'}"})
    versions = list(ctx.db.execute(select(ConfigVersion, ConfigItem.key).join(ConfigItem).where(
        ConfigVersion.organization_id == org, ConfigVersion.decided_at >= since_dt,
        ConfigVersion.decided_at < until_dt, ConfigVersion.decided_by.is_not(None))))
    names |= _user_names(ctx, [v.decided_by for v, _ in versions])
    for v, key in versions:
        out.append({"record": f"{key} v{v.version}", "type": "configuration", "action": v.status,
                    "by": names.get(v.decided_by), "at": v.decided_at, "detail": v.change_summary})
    return sorted(out, key=lambda r: r["at"], reverse=True)


def pending(ctx: TenantContext) -> dict:
    org = ctx.organization_id
    today = ctx.today()
    status = gages._status_sql(ctx)
    gscope = lambda s: _gage_scope(ctx, s, Gage.plant_id)  # noqa: E731
    return {
        "overdue_gages": [{"gage_code": c, "next_due_date": d} for c, d in ctx.db.execute(gscope(
            select(Gage.gage_code, Gage.next_due_date).where(Gage.organization_id == org, status == "OVERDUE"))
            .order_by(Gage.next_due_date))],
        "due_soon_gages": [{"gage_code": c, "next_due_date": d} for c, d in ctx.db.execute(gscope(
            select(Gage.gage_code, Gage.next_due_date).where(Gage.organization_id == org, status == "DUE_SOON"))
            .order_by(Gage.next_due_date))],
        "calibrations_pending_decision": [{"calibration_code": c, "status": s} for c, s in ctx.db.execute(
            _gage_scope(ctx, select(CalibrationActivity.calibration_code, CalibrationActivity.status).where(
                CalibrationActivity.organization_id == org,
                CalibrationActivity.status.in_(("PENDING_REVIEW", "PENDING_APPROVAL", "APPROVED"))),
                CalibrationActivity.plant_id))],
        "open_oot_cases": [{"case_code": c, "status": s} for c, s in ctx.db.execute(_gage_scope(ctx, select(
            OotCase.case_code, OotCase.status).where(OotCase.organization_id == org,
                                                     OotCase.status.not_in(("CLOSED", "CANCELLED"))),
            OotCase.plant_id))],
        "msa_in_review": [{"study_code": c} for (c,) in ctx.db.execute(_gage_scope(ctx, select(
            MsaStudy.study_code).where(MsaStudy.organization_id == org, MsaStudy.status == "IN_REVIEW"),
            MsaStudy.plant_id))],
        "expired_standards": [{"standard_code": c, "valid_until": v} for c, v in ctx.db.execute(_gage_scope(
            ctx, select(Standard.standard_code, Standard.valid_until).where(
                Standard.organization_id == org, Standard.control_status != "INACTIVE",
                or_(Standard.valid_until < today, Standard.valid_until.is_(None))), Standard.plant_id))],
        "authorizations_expiring": [{"user": n, "activity": a, "valid_until": v} for n, a, v in ctx.db.execute(
            select(User.full_name, Authorization.activity, Authorization.valid_until).join(
                User, User.id == Authorization.user_id).where(
                Authorization.organization_id == org, Authorization.revoked_at.is_(None),
                Authorization.valid_until.is_not(None), Authorization.valid_until >= today,
                Authorization.valid_until <= today + timedelta(days=30)))],
        "configuration_drafts": [{"key": k, "version": v} for k, v in ctx.db.execute(
            select(ConfigItem.key, ConfigVersion.version).join(ConfigItem).where(
                ConfigVersion.organization_id == org, ConfigVersion.status == "DRAFT"))],
        "imports_not_committed": [{"filename": f, "created_at": c} for f, c in ctx.db.execute(
            select(ImportJob.filename, ImportJob.created_at).where(ImportJob.organization_id == org,
                                                                   ImportJob.status == "VALIDATED"))],
    }


def export_xlsx(ctx: TenantContext, gage_id: uuid.UUID | None) -> bytes:
    """Workbook with the evidence matrix, pending items, approvals and (optionally) a gage dossier."""
    wb = Workbook()
    ws = wb.active
    ws.title = "matrix"
    ws.append(["Note", DISCLAIMER])
    ws.append([])
    ws.append(["Process", "Description", "State", "Clauses", "Evidence", "Gaps"])
    m = matrix(ctx)
    for p in m["processes"]:
        ws.append([p["process"], p["description"], p["state"], ", ".join(p["clauses"]),
                   "; ".join(f"{k}={v}" for k, v in p["evidence"].items()),
                   "; ".join(f"{k}={v}" for k, v in p["gaps"].items())])
    ws2 = wb.create_sheet("pending")
    for section, rows in pending(ctx).items():
        ws2.append([section, len(rows)])
        for r in rows:
            ws2.append(["", *[str(plain(v)) for v in r.values()]])
    ws3 = wb.create_sheet("approvals")
    ws3.append(["Record", "Type", "Action", "By", "At", "Detail"])
    today = ctx.today()
    for a in approvals(ctx, today - timedelta(days=365), today):
        ws3.append([a["record"], a["type"], a["action"], a["by"], str(plain(a["at"])), a["detail"]])
    if gage_id:
        d = dossier(ctx, gage_id)
        for name in ("calibrations", "certificates", "status_history", "oot_cases", "msa_studies", "audit_trail"):
            s = wb.create_sheet(f"{d['gage']['gage_code'][:12]}-{name}"[:31])
            rows = d[name]
            if rows:
                s.append(list(rows[0].keys()))
                for r in rows:
                    s.append([str(plain(v)) if v is not None else "" for v in r.values()])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
