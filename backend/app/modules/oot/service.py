"""Out-of-tolerance cases: detection, restriction, retrospective analysis, actions and closure."""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.sequences import next_code
from app.modules.audit import service as audit
from app.modules.calibration import service as calibration
from app.modules.calibration.models import CalibrationActivity, CalibrationPoint
from app.modules.configuration import service as config
from app.modules.configuration import workflow
from app.modules.documents.models import Attachment
from app.modules.events import service as events
from app.modules.gages import service as gages
from app.modules.gages.models import Gage, GageMovement
from app.modules.gages.status import ControlStatus
from app.modules.identity.deps import TenantContext
from app.modules.identity.permissions import P
from app.modules.laboratory.models import InspectionResult, ServiceRequest, WorkOrder
from app.modules.msa.models import MsaObservation, MsaStudy
from app.modules.notifications.service import notify, users_with_permission
from app.modules.oot.models import CLOSE_REQUIREMENTS, OotAction, OotCase, OotImpactItem, OotSettings

ENTITY = "oot_case"
OPEN_STATES_EXCLUDED = ("CLOSED", "CANCELLED")
DEFAULT_CLOSE = ["risk_assessment", "disposition", "impact_items_assessed", "actions_completed",
                 "customer_notification_decided", "gage_released_or_retired"]
INVESTIGATION_FIELDS = ["description", "responsible_id", "risk_level", "risk_assessment", "investigation_scope",
                        "reinspection", "containment", "disposition", "corrective_actions",
                        "customer_notification_required", "customer_notification", "customer_notified_on",
                        "limitations"]
# Other modules (integrations: device readings) may add impact sources: f(ctx, case, start_dt, end_dt) -> items.
impact_sources: list = []


# ---------------------------------------------------------------- settings

def settings(ctx: TenantContext) -> OotSettings:
    s = ctx.db.get(OotSettings, ctx.organization_id)
    return s or OotSettings(organization_id=ctx.organization_id, restrict_on_detection=True,
                            auto_create_from_calibration=True, close_requirements=list(DEFAULT_CLOSE), version=0)


def update_settings(ctx: TenantContext, data: dict) -> OotSettings:
    bad = [r for r in data["close_requirements"] if r not in CLOSE_REQUIREMENTS]
    if bad:
        raise BusinessRuleError("Unknown close requirements", code="invalid_settings", details=bad)
    current = ctx.db.get(OotSettings, ctx.organization_id)
    before = audit.snapshot(current, ["restrict_on_detection", "auto_create_from_calibration",
                                      "close_requirements", "version"]) if current else {}
    if current is None:
        current = OotSettings(organization_id=ctx.organization_id, version=0, updated_by=ctx.user_id, **data)
        ctx.db.add(current)
    else:
        for k, v in data.items():
            setattr(current, k, v)
    current.version = (current.version or 0) + 1
    current.updated_by = ctx.user_id
    ctx.audit(action="oot.settings_updated", entity_type="oot_settings", entity_id=ctx.organization_id,
              changes={"before": before, "after": data | {"version": current.version}})
    ctx.db.commit()
    return current


# ---------------------------------------------------------------- queries

def get_case(ctx: TenantContext, case_id: uuid.UUID, *, for_update: bool = False) -> OotCase:
    stmt = select(OotCase).where(OotCase.id == case_id, OotCase.organization_id == ctx.organization_id)
    if for_update:
        stmt = stmt.with_for_update(of=OotCase)
    c = ctx.db.scalar(stmt.execution_options(populate_existing=True))
    if c is None or not ctx.can_access_plant(c.plant_id):
        raise NotFoundError("OOT case not found")
    return c


def list_cases(ctx: TenantContext, *, gage_id=None, status=None, open_only=False) -> list[OotCase]:
    stmt = select(OotCase).where(OotCase.organization_id == ctx.organization_id)
    if ctx.plant_ids is not None:
        stmt = stmt.where(OotCase.plant_id.in_(ctx.plant_ids))
    if gage_id:
        stmt = stmt.where(OotCase.gage_id == gage_id)
    if status:
        stmt = stmt.where(OotCase.status == status)
    if open_only:
        stmt = stmt.where(OotCase.status.not_in(OPEN_STATES_EXCLUDED))
    return list(ctx.db.scalars(stmt.order_by(OotCase.created_at.desc()).limit(500)))


def _open_restricting_case(ctx: TenantContext, gage_id: uuid.UUID) -> OotCase | None:
    return ctx.db.scalar(select(OotCase).where(
        OotCase.organization_id == ctx.organization_id, OotCase.gage_id == gage_id,
        OotCase.restriction_applied.is_(True), OotCase.gage_released_at.is_(None),
        OotCase.status.not_in(OPEN_STATES_EXCLUDED)).limit(1))


# ---------------------------------------------------------------- detection and restriction

def _points(ctx: TenantContext, a: CalibrationActivity, phase: str) -> list[dict]:
    out = []
    for p in calibration.current_points(ctx, a):
        if p.phase != phase:
            continue
        dev = Decimal(0)
        if p.measured > p.upper_limit:
            dev = p.measured - p.upper_limit
        elif p.measured < p.lower_limit:
            dev = p.measured - p.lower_limit
        out.append({"sequence": p.sequence, "description": p.description, "nominal": audit.plain(p.nominal),
                    "lower": audit.plain(p.lower_limit), "upper": audit.plain(p.upper_limit),
                    "measured": audit.plain(p.measured), "unit": p.unit, "in_tolerance": p.in_tolerance,
                    "deviation_outside": audit.plain(dev)})
    return out


def _restrict(ctx: TenantContext, case: OotCase, gage: Gage) -> None:
    if case.restriction_applied:
        return
    case.gage_prior_control_status = gage.control_status
    case.restriction_applied = True
    if gage.control_status in (ControlStatus.ACTIVE.value, ControlStatus.IN_CALIBRATION.value):
        gages.apply_control_status(ctx, gage, ControlStatus.OUT_OF_SERVICE, f"OOT case {case.case_code} detected",
                                   "gage.restricted", {"oot_case": case.case_code})


def create_case(ctx: TenantContext, *, gage: Gage, description: str, responsible_id: uuid.UUID,
                detected_on: date, source: str, activity: CalibrationActivity | None = None,
                found_result: str | None = None, tolerance: str | None = None,
                max_deviation: Decimal | None = None, custom_fields: dict | None = None) -> OotCase:
    """Register a case in the current transaction (no commit) and apply the configured restriction."""
    cfg = settings(ctx)
    config.apply_values(ctx, ENTITY, None, custom_fields, creating=True)
    as_found = as_left = None
    if activity is not None:
        as_found, as_left = _points(ctx, activity, "AS_FOUND"), _points(ctx, activity, "AS_LEFT")
        oot = [p for p in as_found if not p["in_tolerance"]]
        if max_deviation is None and oot:
            max_deviation = max(abs(Decimal(p["deviation_outside"])) for p in oot)
        if found_result is None:
            found_result = "; ".join(f"#{p['sequence']} {p['description'] or ''} measured {p['measured']} "
                                     f"(limits {p['lower']} .. {p['upper']} {p['unit'] or ''})" for p in oot)[:500] \
                or f"As Found out of tolerance ({activity.calibration_code})"
        if tolerance is None and oot:
            tolerance = f"{oot[0]['lower']} .. {oot[0]['upper']} {oot[0]['unit'] or ''}".strip()
    version = workflow.version_for_new(ctx, ENTITY)
    case = OotCase(organization_id=ctx.organization_id, plant_id=gage.plant_id, gage_id=gage.id,
                   calibration_id=activity.id if activity else None, detection_source=source,
                   detected_on=detected_on, description=description, found_result=found_result,
                   tolerance=tolerance, max_deviation=max_deviation, as_found=as_found, as_left=as_left,
                   responsible_id=responsible_id, created_by=ctx.user_id, workflow_version=version,
                   status=workflow.initial_state(ctx, ENTITY, version),
                   case_code=next_code(ctx.db, ctx.organization_id, "OOT", detected_on.year))
    ctx.db.add(case)
    ctx.db.flush()
    config.apply_values(ctx, ENTITY, case.id, custom_fields, creating=True)
    ctx.audit(action="oot.case_created", entity_type=ENTITY, entity_id=case.id,
              changes={"case_code": case.case_code, "gage_code": gage.gage_code, "source": source,
                       "calibration": activity.calibration_code if activity else None,
                       "max_deviation": audit.plain(max_deviation)})
    workflow.record_created(ctx, ENTITY, case, case.id)
    if cfg.restrict_on_detection:
        _restrict(ctx, case, gage)
        workflow.system_transition(ctx, ENTITY, case, case.id, "RESTRICTED",
                                   "Restriction applied automatically on detection (configuration)")
    events.emit(ctx.db, ctx.organization_id, "oot.case_created", ENTITY, case.id,
                {"case_code": case.case_code, "gage_id": gage.id, "gage_code": gage.gage_code,
                 "calibration_id": case.calibration_id, "detected_on": detected_on,
                 "restricted": case.restriction_applied})
    notify(ctx, set(users_with_permission(ctx, P.OOT_MANAGE)) | {gage.responsible_user_id, responsible_id},
           "oot.case_created", f"OOT {case.case_code}: {gage.gage_code}", found_result, f"/oot/{case.id}",
           include_actor=False)
    ctx.db.flush()
    return case


def create_manual(ctx: TenantContext, data: dict) -> OotCase:
    gage = gages.get_gage(ctx, data["gage_id"], for_update=True)
    gages.ensure_active_member(ctx, data["responsible_id"], "invalid_responsible")
    activity = None
    if data.get("calibration_id"):
        activity = calibration.get_activity(ctx, data["calibration_id"])
        if activity.gage_id != gage.id or activity.status != "RELEASED":
            raise BusinessRuleError("The calibration must be a released activity of the same gage",
                                    code="invalid_calibration")
        if ctx.db.scalar(select(OotCase.id).where(OotCase.calibration_id == activity.id)):
            raise ConflictError("An OOT case already exists for this calibration", code="duplicate_case")
    if data["detected_on"] > ctx.today():
        raise BusinessRuleError("The detection date cannot be in the future", code="invalid_date")
    case = create_case(ctx, gage=gage, description=data["description"], responsible_id=data["responsible_id"],
                       detected_on=data["detected_on"], source="MANUAL", activity=activity,
                       found_result=data.get("found_result"), tolerance=data.get("tolerance"),
                       max_deviation=data.get("max_deviation"), custom_fields=data.get("custom_fields"))
    ctx.db.commit()
    return get_case(ctx, case.id)


def on_calibration_released(ctx: TenantContext, a: CalibrationActivity, gage: Gage) -> None:
    """Calibration release hook: an As Found out of tolerance opens a case automatically."""
    if a.as_found_in_tolerance is not False or not settings(ctx).auto_create_from_calibration:
        return
    if ctx.db.scalar(select(OotCase.id).where(OotCase.calibration_id == a.id)):
        return
    create_case(ctx, gage=gage, activity=a, source="CALIBRATION", detected_on=a.performed_date,
                responsible_id=gage.responsible_user_id or a.approver_id or ctx.user_id,
                description=f"As Found out of tolerance detected by {a.calibration_code} "
                            f"({a.activity_type.replace('_', ' ').lower()}).")


def _hold(ctx: TenantContext, gage: Gage) -> str | None:
    case = _open_restricting_case(ctx, gage.id)
    return f"restricted by OOT case {case.case_code}" if case else None


def _guard(ctx: TenantContext, gage: Gage, target: ControlStatus) -> None:
    if target == ControlStatus.ACTIVE:
        case = _open_restricting_case(ctx, gage.id)
        if case:
            raise ConflictError(f"The gage is restricted by OOT case {case.case_code}; it can only be released "
                                "from the case by an authorized approver", code="oot_restriction",
                                details={"case": case.case_code})


calibration.release_hooks.append(on_calibration_released)
gages.restriction_holders.append(_hold)
gages.release_guards.append(_guard)


def release_gage(ctx: TenantContext, case_id: uuid.UUID, reason: str) -> OotCase:
    case = get_case(ctx, case_id, for_update=True)
    workflow.ensure_capability(ctx, ENTITY, case, "release_gage")
    ctx.ensure(P.GAGES_RELEASE)
    config.ensure_approval(ctx, ENTITY, "RELEASE", plant_id=case.plant_id)
    if not case.restriction_applied or case.gage_released_at is not None:
        raise ConflictError("The case holds no restriction on the gage", code="not_restricted")
    gage = gages.get_gage(ctx, case.gage_id, for_update=True)
    if gage.control_status != ControlStatus.OUT_OF_SERVICE.value:
        raise ConflictError(f"The gage is {gage.control_status}", code="invalid_gage_status")
    verified = ctx.db.scalar(select(CalibrationActivity).where(
        CalibrationActivity.gage_id == gage.id, CalibrationActivity.status == "RELEASED",
        CalibrationActivity.performed_date >= case.detected_on, CalibrationActivity.result != "FAIL",
        CalibrationActivity.as_left_in_tolerance.is_not(False)).order_by(CalibrationActivity.performed_date.desc())
        .limit(1))
    if verified is None:
        raise BusinessRuleError("No released calibration with an acceptable As Left on or after the detection date",
                                code="gage_not_verified")
    case.gage_released_at, case.gage_released_by, case.gage_release_reason = datetime.now(UTC), ctx.user_id, reason
    ctx.db.flush()
    target = ControlStatus.ACTIVE
    gages.apply_control_status(ctx, gage, target, f"Released from OOT case {case.case_code}: {reason}",
                               "gage.released", {"oot_case": case.case_code, "verified_by": verified.calibration_code})
    ctx.audit(action="oot.gage_released", entity_type=ENTITY, entity_id=case.id, reason=reason,
              changes={"gage_code": gage.gage_code, "verified_by": verified.calibration_code})
    ctx.db.commit()
    return get_case(ctx, case.id)


# ---------------------------------------------------------------- investigation

def update_investigation(ctx: TenantContext, case_id: uuid.UUID, data: dict) -> OotCase:
    case = get_case(ctx, case_id, for_update=True)
    workflow.ensure_capability(ctx, ENTITY, case, "investigate")
    if "responsible_id" in data:
        gages.ensure_active_member(ctx, data["responsible_id"], "invalid_responsible")
    if data.get("customer_notified_on") and data["customer_notified_on"] > ctx.today():
        raise BusinessRuleError("customer_notified_on cannot be in the future", code="invalid_date")
    before = audit.snapshot(case, INVESTIGATION_FIELDS)
    for k, v in data.items():
        setattr(case, k, v)
    changes = audit.diff(before, audit.snapshot(case, INVESTIGATION_FIELDS))
    if changes:
        ctx.audit(action="oot.investigation_updated", entity_type=ENTITY, entity_id=case.id, changes=changes)
    ctx.db.commit()
    return get_case(ctx, case.id)


def _last_acceptable(ctx: TenantContext, case: OotCase) -> CalibrationActivity | None:
    stmt = select(CalibrationActivity).where(
        CalibrationActivity.gage_id == case.gage_id, CalibrationActivity.status == "RELEASED",
        CalibrationActivity.result != "FAIL", CalibrationActivity.as_left_in_tolerance.is_not(False),
        CalibrationActivity.performed_date < case.detected_on)
    if case.calibration_id:
        stmt = stmt.where(CalibrationActivity.id != case.calibration_id)
    return ctx.db.scalar(stmt.order_by(CalibrationActivity.performed_date.desc()).limit(1))


def generate_analysis(ctx: TenantContext, case_id: uuid.UUID) -> OotCase:
    """Identify the potentially affected period and the records in it.

    Re-running adds newly found records and keeps the assessments already made.
    """
    case = get_case(ctx, case_id, for_update=True)
    workflow.ensure_capability(ctx, ENTITY, case, "analyze")
    gage = gages.get_gage(ctx, case.gage_id)
    limitations = []
    last = _last_acceptable(ctx, case)
    if last is not None:
        start = last.performed_date
        case.last_acceptable_calibration_id = last.id
    else:
        start = gage.in_service_date or gage.acquisition_date or gage.created_at.date()
        case.last_acceptable_calibration_id = None
        limitations.append(f"No earlier acceptable calibration is recorded; the period starts at "
                           f"{start.isoformat()} (gage in service / registration date).")
    end = case.detected_on
    case.impact_start, case.impact_end = start, end
    start_dt = datetime.combine(start, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC)
    existing = {(i.item_type, i.ref_id) for i in ctx.db.scalars(select(OotImpactItem).where(
        OotImpactItem.case_id == case.id))}
    added = 0

    def add(item_type, ref_id, ref_code, description, occurred_at, data):
        nonlocal added
        if (item_type, ref_id) in existing:
            return
        existing.add((item_type, ref_id))
        ctx.db.add(OotImpactItem(organization_id=ctx.organization_id, case_id=case.id, item_type=item_type,
                                 source="SYSTEM", ref_id=ref_id, ref_code=ref_code, description=description[:1000],
                                 occurred_at=occurred_at, data=data, created_by=ctx.user_id))
        added += 1

    rows = ctx.db.execute(
        select(InspectionResult, WorkOrder.work_order_code, ServiceRequest.request_code, ServiceRequest.customer_name)
        .join(WorkOrder, WorkOrder.id == InspectionResult.work_order_id)
        .join(ServiceRequest, ServiceRequest.id == WorkOrder.service_request_id)
        .where(InspectionResult.organization_id == ctx.organization_id, InspectionResult.gage_id == gage.id,
               InspectionResult.superseded.is_(False), InspectionResult.measured_at >= start_dt,
               InspectionResult.measured_at < end_dt)).all()
    orders: dict = {}
    for r, wo_code, req_code, customer in rows:
        add("INSPECTION_RESULT", r.id, wo_code,
            f"{r.part_number} {r.drawing_revision or ''} char {r.characteristic_number} {r.characteristic}: "
            f"{audit.plain(r.measured)} {r.unit} [{audit.plain(r.lower_limit)}, {audit.plain(r.upper_limit)}] "
            f"-> {r.result}", r.measured_at,
            {"work_order": wo_code, "request": req_code, "customer": customer, "part_number": r.part_number,
             "characteristic": r.characteristic, "measured": audit.plain(r.measured), "result": r.result,
             "gage_status_at_measurement": r.gage_status, "sample_id": r.sample_id})
        orders.setdefault(r.work_order_id, (wo_code, req_code, customer, r.measured_at, set()))[4].add(r.part_number)
    for wo_id, (wo_code, req_code, customer, at, parts) in orders.items():
        add("WORK_ORDER", wo_id, wo_code, f"Work order {wo_code} (request {req_code}, customer {customer or '-'}) "
                                          f"used the gage; parts {', '.join(sorted(parts))}", at,
            {"request": req_code, "customer": customer, "parts": sorted(parts)})
    for m in ctx.db.scalars(select(GageMovement).where(
            GageMovement.gage_id == gage.id, GageMovement.organization_id == ctx.organization_id,
            GageMovement.moved_at >= start_dt, GageMovement.moved_at < end_dt)):
        add("GAGE_MOVEMENT", m.id, None, f"Assignment change: {m.reason}", m.moved_at, {"changes": m.changes})
    studies = ctx.db.execute(select(MsaStudy.id, MsaStudy.study_code, MsaStudy.title, func.count(MsaObservation.id))
                             .join(MsaObservation, MsaObservation.study_id == MsaStudy.id)
                             .where(MsaStudy.gage_id == gage.id, MsaStudy.organization_id == ctx.organization_id,
                                    MsaObservation.recorded_at >= start_dt, MsaObservation.recorded_at < end_dt)
                             .group_by(MsaStudy.id, MsaStudy.study_code, MsaStudy.title)).all()
    for sid, code, title, n in studies:
        add("MSA_STUDY", sid, code, f"MSA study {code} '{title}' recorded {n} readings with the gage", None,
            {"readings": n})
    for source in impact_sources:
        for item in source(ctx, case, start_dt, end_dt):
            add(**item)
    limitations.append("Gage Tracker does not hold production lot or shipment data: products and lots measured "
                       "outside the laboratory module must be identified and recorded manually.")
    if not rows:
        limitations.append("No laboratory inspection results with this gage were found in the period.")
    case.limitations = "\n".join(limitations)
    case.analysis_generated_at = datetime.now(UTC)
    ctx.audit(action="oot.analysis_generated", entity_type=ENTITY, entity_id=case.id,
              changes={"impact_start": start.isoformat(), "impact_end": end.isoformat(), "items_added": added,
                       "last_acceptable": last.calibration_code if last else None})
    ctx.db.commit()
    return get_case(ctx, case.id)


def items(ctx: TenantContext, case_id: uuid.UUID) -> list[OotImpactItem]:
    get_case(ctx, case_id)
    return list(ctx.db.scalars(select(OotImpactItem).where(OotImpactItem.case_id == case_id)
                               .order_by(OotImpactItem.item_type, OotImpactItem.occurred_at.nulls_last())))


def add_manual_item(ctx: TenantContext, case_id: uuid.UUID, data: dict) -> OotImpactItem:
    case = get_case(ctx, case_id, for_update=True)
    workflow.ensure_capability(ctx, ENTITY, case, "analyze")
    item = OotImpactItem(organization_id=ctx.organization_id, case_id=case.id, item_type="MANUAL", source="MANUAL",
                         created_by=ctx.user_id, **data)
    ctx.db.add(item)
    ctx.db.flush()
    ctx.audit(action="oot.impact_item_added", entity_type=ENTITY, entity_id=case.id,
              changes={"ref_code": data.get("ref_code"), "description": data["description"]})
    ctx.db.commit()
    return item


def assess_item(ctx: TenantContext, item_id: uuid.UUID, assessment: str, note: str | None) -> OotImpactItem:
    item = ctx.db.scalar(select(OotImpactItem).where(OotImpactItem.id == item_id,
                                                     OotImpactItem.organization_id == ctx.organization_id))
    if item is None:
        raise NotFoundError("Impact item not found")
    case = get_case(ctx, item.case_id, for_update=True)
    workflow.ensure_capability(ctx, ENTITY, case, "analyze")
    if assessment in ("IMPACT", "REINSPECT") and not (note or "").strip():
        raise BusinessRuleError("Describe the impact or the reinspection needed", code="comment_required")
    before = item.assessment
    item.assessment, item.assessment_note = assessment, note
    item.assessed_by, item.assessed_at = ctx.user_id, datetime.now(UTC)
    ctx.audit(action="oot.impact_assessed", entity_type=ENTITY, entity_id=case.id, reason=note,
              changes={"item": str(item.id), "assessment": [before, assessment]})
    ctx.db.commit()
    return item


# ---------------------------------------------------------------- actions

def actions(ctx: TenantContext, case_id: uuid.UUID) -> list[OotAction]:
    get_case(ctx, case_id)
    return list(ctx.db.scalars(select(OotAction).where(OotAction.case_id == case_id).order_by(OotAction.created_at)))


def add_action(ctx: TenantContext, case_id: uuid.UUID, data: dict) -> OotAction:
    case = get_case(ctx, case_id, for_update=True)
    workflow.ensure_capability(ctx, ENTITY, case, "act")
    gages.ensure_active_member(ctx, data["owner_id"], "invalid_owner")
    a = OotAction(organization_id=ctx.organization_id, case_id=case.id, created_by=ctx.user_id, **data)
    ctx.db.add(a)
    ctx.db.flush()
    ctx.audit(action="oot.action_added", entity_type=ENTITY, entity_id=case.id,
              changes={"action": str(a.id), "type": a.action_type, "description": a.description,
                       "due_date": audit.plain(a.due_date)})
    notify(ctx, [a.owner_id], "oot.action_assigned", f"{case.case_code}: {a.action_type.lower()}", a.description,
           f"/oot/{case.id}")
    ctx.db.commit()
    return a


def finish_action(ctx: TenantContext, action_id: uuid.UUID, done: bool, note: str) -> OotAction:
    a = ctx.db.scalar(select(OotAction).where(OotAction.id == action_id,
                                              OotAction.organization_id == ctx.organization_id).with_for_update())
    if a is None:
        raise NotFoundError("Action not found")
    case = get_case(ctx, a.case_id)
    workflow.ensure_capability(ctx, ENTITY, case, "act")
    if a.status != "OPEN":
        raise ConflictError("The action is not open", code="invalid_status")
    if a.owner_id != ctx.user_id:
        ctx.ensure(P.OOT_APPROVE)
    a.status = "DONE" if done else "CANCELLED"
    a.result_note, a.completed_by, a.completed_at = note, ctx.user_id, datetime.now(UTC)
    ctx.audit(action="oot.action_" + ("completed" if done else "cancelled"), entity_type=ENTITY, entity_id=case.id,
              reason=note, changes={"action": str(a.id), "type": a.action_type})
    ctx.db.commit()
    return a


# ---------------------------------------------------------------- workflow adapter

def close_gaps(ctx: TenantContext, case: OotCase, requirements: list[str] | None = None) -> list[str]:
    reqs = requirements if requirements is not None else settings(ctx).close_requirements
    gaps = []
    its = list(ctx.db.scalars(select(OotImpactItem.assessment).where(OotImpactItem.case_id == case.id)))
    acts = list(ctx.db.scalars(select(OotAction).where(OotAction.case_id == case.id)))
    checks = {
        "risk_assessment": bool(case.risk_level and (case.risk_assessment or "").strip()),
        "disposition": bool((case.disposition or "").strip()),
        "corrective_actions": bool((case.corrective_actions or "").strip())
        or any(a.action_type == "CORRECTIVE" and a.status == "DONE" for a in acts),
        "impact_items_assessed": case.analysis_generated_at is not None and "PENDING" not in its,
        "actions_completed": all(a.status != "OPEN" for a in acts),
        "customer_notification_decided": case.customer_notification_required is False
        or (case.customer_notification_required is True and case.customer_notified_on is not None),
        "evidence_attached": bool(ctx.db.scalar(select(Attachment.id).where(
            Attachment.entity_type == ENTITY, Attachment.entity_id == case.id, Attachment.removed_at.is_(None))
            .limit(1))),
        "gage_released_or_retired": not case.restriction_applied or case.gage_released_at is not None
        or case.gage.control_status == ControlStatus.INACTIVE.value,
    }
    for r in reqs:
        if not checks.get(r, False):
            gaps.append(r)
    return gaps


def _facts(ctx: TenantContext, case: OotCase) -> dict:
    its = list(ctx.db.scalars(select(OotImpactItem.assessment).where(OotImpactItem.case_id == case.id)))
    acts = list(ctx.db.scalars(select(OotAction.status).where(OotAction.case_id == case.id)))
    return {
        "risk_level": case.risk_level,
        "has_risk_assessment": bool((case.risk_assessment or "").strip()),
        "has_disposition": bool((case.disposition or "").strip()),
        "has_corrective_actions": bool((case.corrective_actions or "").strip()),
        "open_actions": acts.count("OPEN"),
        "pending_impact_items": its.count("PENDING"),
        "impacted_items": its.count("IMPACT") + its.count("REINSPECT"),
        "analysis_generated": case.analysis_generated_at is not None,
        "customer_notification_required": case.customer_notification_required,
        "customer_notified": case.customer_notified_on is not None,
        "gage_released": case.gage_released_at is not None,
        "max_deviation": float(case.max_deviation) if case.max_deviation is not None else None,
    }


def _before_enter(ctx: TenantContext, case: OotCase, state: str) -> None:
    if state == "RESTRICTED":
        _restrict(ctx, case, gages.get_gage(ctx, case.gage_id, for_update=True))
    if state == "IMPACT_EVALUATION" and case.analysis_generated_at is None:
        raise BusinessRuleError("Generate the retrospective analysis first", code="analysis_required")
    if state == "ACTIONS" and not case.risk_level:
        raise BusinessRuleError("Record the risk evaluation first", code="risk_required")
    if state == "CLOSED":
        gaps = close_gaps(ctx, case)
        if gaps:
            raise BusinessRuleError("The case cannot be closed: required records are missing",
                                    code="close_requirements", details=gaps)


def _after_enter(ctx: TenantContext, case: OotCase, from_state: str, to_state: str) -> None:
    if to_state == "CLOSED":
        case.closed_at = datetime.now(UTC)
    if to_state == "CANCELLED" and case.restriction_applied and case.gage_released_at is None:
        gage = gages.get_gage(ctx, case.gage_id, for_update=True)
        case.gage_released_at, case.gage_released_by = datetime.now(UTC), ctx.user_id
        case.gage_release_reason = "Case cancelled"
        if gage.control_status == ControlStatus.OUT_OF_SERVICE.value and case.gage_prior_control_status == "ACTIVE":
            gages.apply_control_status(ctx, gage, ControlStatus.ACTIVE, f"OOT case {case.case_code} cancelled",
                                       "gage.released", {"oot_case": case.case_code})
    notify(ctx, [case.responsible_id, case.created_by], "oot.status_changed",
           f"{case.case_code}: {from_state} -> {to_state}", case.gage.gage_code, f"/oot/{case.id}")


def _set_state(ctx: TenantContext, case: OotCase, state: str) -> None:
    case.status = state


def _load(ctx: TenantContext, case_id: uuid.UUID, for_update: bool = False) -> OotCase:
    ctx.ensure(P.OOT_READ)
    return get_case(ctx, case_id, for_update=for_update)


DEFAULT_WORKFLOW = {
    "entity_type": ENTITY,
    "initial": "DETECTED",
    "states": [
        {"code": "DETECTED", "label": "Detected", "capabilities": ["investigate"]},
        {"code": "RESTRICTED", "label": "Gage restricted", "capabilities": ["investigate"]},
        {"code": "INVESTIGATION", "label": "Investigation",
         "capabilities": ["investigate", "analyze", "act", "release_gage"]},
        {"code": "IMPACT_EVALUATION", "label": "Impact evaluation",
         "capabilities": ["investigate", "analyze", "act", "release_gage"]},
        {"code": "ACTIONS", "label": "Actions", "capabilities": ["investigate", "act", "release_gage"]},
        {"code": "IN_REVIEW", "label": "Review", "capabilities": ["act", "release_gage"]},
        {"code": "PENDING_APPROVAL", "label": "Pending approval", "capabilities": ["act", "release_gage"]},
        {"code": "APPROVED", "label": "Approved", "capabilities": ["act", "release_gage"]},
        {"code": "CLOSED", "label": "Closed", "capabilities": []},
        {"code": "CANCELLED", "label": "Cancelled", "capabilities": []},
    ],
    "transitions": [
        {"code": "RESTRICT", "label": "Restrict gage", "from_states": ["DETECTED"], "to": "RESTRICTED",
         "permission": P.OOT_MANAGE},
        {"code": "INVESTIGATE", "label": "Start investigation", "from_states": ["DETECTED", "RESTRICTED"],
         "to": "INVESTIGATION", "permission": P.OOT_MANAGE},
        {"code": "EVALUATE_IMPACT", "label": "Evaluate impact", "from_states": ["INVESTIGATION"],
         "to": "IMPACT_EVALUATION", "permission": P.OOT_MANAGE},
        {"code": "PLAN_ACTIONS", "label": "Define actions", "from_states": ["IMPACT_EVALUATION"], "to": "ACTIONS",
         "permission": P.OOT_MANAGE},
        {"code": "SUBMIT", "label": "Submit for review", "from_states": ["ACTIONS"], "to": "IN_REVIEW",
         "permission": P.OOT_MANAGE},
        {"code": "REVIEW", "label": "Technical review OK", "from_states": ["IN_REVIEW"], "to": "PENDING_APPROVAL",
         "permission": P.OOT_MANAGE, "action": "REVIEW", "segregate_from": ["previous_actor"]},
        {"code": "RETURN", "label": "Return to actions", "from_states": ["IN_REVIEW", "PENDING_APPROVAL"],
         "to": "ACTIONS", "permission": P.OOT_MANAGE, "action": "REJECT", "require_comment": True},
        {"code": "APPROVE", "label": "Approve", "from_states": ["PENDING_APPROVAL"], "to": "APPROVED",
         "permission": P.OOT_APPROVE, "action": "APPROVE", "segregate_from": ["responsible", "previous_actor"]},
        {"code": "CLOSE", "label": "Close case", "from_states": ["APPROVED"], "to": "CLOSED",
         "permission": P.OOT_APPROVE},
        {"code": "CANCEL", "label": "Cancel (registered in error)",
         "from_states": ["DETECTED", "RESTRICTED", "INVESTIGATION"], "to": "CANCELLED",
         "permission": P.OOT_APPROVE, "action": "CANCEL", "require_comment": True},
    ],
    "escalations": [],
}
