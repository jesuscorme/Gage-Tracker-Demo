"""Calibration Management workflow.

    PLANNED -> REQUESTED -> SCHEDULED -> IN_PROGRESS -> PENDING_REVIEW -> PENDING_APPROVAL
            -> APPROVED -> RELEASED            (review / approval can return to IN_PROGRESS)
    any state before APPROVED -> CANCELLED

Key rules
* Activity types (external / internal calibration, routine verification) are distinct
  records; whether each is enabled and which evidence it needs comes from
  ``calibration_settings`` (plant row overrides organization row).
* As Found and As Left points are separate, append-only rows; corrections supersede.
* Executing internal calibrations / verifications, technical review and approval each
  require a current personal authorization (Competency Management). Reviewer and
  approver must be different people, and neither can be the performer.
* Standards are checked for validity on the performed date; expired/restricted ones
  need a documented exception.
* Release updates the gage (dates and status) in the same transaction as the activity.
  A verification never moves the calibration due date.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.sequences import next_code
from app.modules.audit import service as audit
from app.modules.calibration.models import (
    ACTIVITY_TYPES,
    CalibrationActivity,
    CalibrationCertificate,
    CalibrationPoint,
    CalibrationSetting,
    CalibrationStandardUsage,
    CalibrationStatusHistory,
)
from app.modules.competency import service as competency
from app.modules.documents import service as documents
from app.modules.documents.models import Attachment
from app.modules.gages import service as gages
from app.modules.gages.models import Gage
from app.modules.gages.status import ControlStatus
from app.modules.identity.deps import TenantContext
from app.modules.identity.permissions import P
from app.modules.notifications.service import notify
from app.modules.organizations.router import get_plant
from app.modules.standards import service as standards

CALIBRATION_TYPES = {"EXTERNAL_CALIBRATION", "INTERNAL_CALIBRATION"}
EXECUTION_ACTIVITY = {"INTERNAL_CALIBRATION": "INTERNAL_CALIBRATION", "ROUTINE_VERIFICATION": "ROUTINE_VERIFICATION"}
OPEN = ("PLANNED", "REQUESTED", "SCHEDULED", "IN_PROGRESS", "PENDING_REVIEW", "PENDING_APPROVAL", "APPROVED")
HOLDING_GAGE = ("IN_PROGRESS", "PENDING_REVIEW", "PENDING_APPROVAL", "APPROVED")
PRE_EXECUTION = ("PLANNED", "REQUESTED", "SCHEDULED")

DEFAULTS = {
    "EXTERNAL_CALIBRATION": dict(enabled=True, require_certificate=True, require_standard=False,
                                 require_as_found=False, require_environment=False),
    "INTERNAL_CALIBRATION": dict(enabled=True, require_certificate=False, require_standard=True,
                                 require_as_found=True, require_environment=True),
    "ROUTINE_VERIFICATION": dict(enabled=True, require_certificate=False, require_standard=True,
                                 require_as_found=True, require_environment=False),
}
SETTING_FIELDS = list(DEFAULTS["EXTERNAL_CALIBRATION"])


# ---------------------------------------------------------------- settings


def effective_settings(ctx: TenantContext, plant_id: uuid.UUID | None) -> dict[str, dict]:
    rows = list(ctx.db.scalars(select(CalibrationSetting).where(
        CalibrationSetting.organization_id == ctx.organization_id,
        (CalibrationSetting.plant_id.is_(None)) | (CalibrationSetting.plant_id == plant_id))))
    out = {t: dict(DEFAULTS[t], source="default") for t in ACTIVITY_TYPES}
    for scope in (None, plant_id):
        for r in rows:
            if r.plant_id == scope and (scope is None or plant_id is not None):
                out[r.activity_type] = {f: getattr(r, f) for f in SETTING_FIELDS} | {
                    "source": "plant" if scope else "organization"}
    return out


def save_setting(ctx: TenantContext, plant_id: uuid.UUID | None, activity_type: str, values: dict) -> dict:
    if plant_id:
        get_plant(ctx, plant_id)
    row = ctx.db.scalar(select(CalibrationSetting).where(
        CalibrationSetting.organization_id == ctx.organization_id, CalibrationSetting.activity_type == activity_type,
        CalibrationSetting.plant_id.is_(None) if plant_id is None else CalibrationSetting.plant_id == plant_id))
    before = {f: getattr(row, f) for f in SETTING_FIELDS} if row else effective_settings(ctx, plant_id)[activity_type]
    if row is None:
        row = CalibrationSetting(organization_id=ctx.organization_id, plant_id=plant_id, activity_type=activity_type,
                                 updated_by=ctx.user_id, **values)
        ctx.db.add(row)
    else:
        for k, v in values.items():
            setattr(row, k, v)
        row.updated_by = ctx.user_id
    ctx.audit(action="calibration.settings_updated", entity_type="calibration_settings", entity_id=plant_id,
              changes={"activity_type": activity_type} | audit.diff({k: before[k] for k in SETTING_FIELDS}, values))
    ctx.db.commit()
    return effective_settings(ctx, plant_id)


# ---------------------------------------------------------------- helpers


def get_activity(ctx: TenantContext, activity_id: uuid.UUID, *, for_update: bool = False) -> CalibrationActivity:
    stmt = select(CalibrationActivity).where(CalibrationActivity.id == activity_id,
                                             CalibrationActivity.organization_id == ctx.organization_id)
    if for_update:
        stmt = stmt.with_for_update(of=CalibrationActivity)
    a = ctx.db.scalar(stmt)
    if a is None or not ctx.can_access_plant(a.plant_id):
        raise NotFoundError("Calibration activity not found")
    return a


def _require_status(a: CalibrationActivity, *allowed: str) -> None:
    if a.status not in allowed:
        raise ConflictError(f"Not allowed while the activity is {a.status}", code="invalid_activity_status",
                            details={"status": a.status, "allowed": list(allowed)})


def _move(ctx: TenantContext, a: CalibrationActivity, to: str, comment: str | None = None, data: dict | None = None):
    ctx.db.add(CalibrationStatusHistory(organization_id=ctx.organization_id, calibration_id=a.id,
                                        from_status=a.status, to_status=to, comment=comment, data=data,
                                        changed_by=ctx.user_id))
    ctx.audit(action=f"calibration.{to.lower()}", entity_type="calibration", entity_id=a.id, reason=comment,
              changes={"status": [a.status, to], "calibration_code": a.calibration_code} | (data or {}))
    a.status = to


def current_points(ctx: TenantContext, a: CalibrationActivity) -> list[CalibrationPoint]:
    return list(ctx.db.scalars(select(CalibrationPoint).where(
        CalibrationPoint.calibration_id == a.id, CalibrationPoint.superseded.is_(False))
        .order_by(CalibrationPoint.phase, CalibrationPoint.sequence)))


def _setting(ctx: TenantContext, a: CalibrationActivity) -> dict:
    return effective_settings(ctx, a.plant_id)[a.activity_type]


def _check_execution_authorization(ctx: TenantContext, a: CalibrationActivity, user_id: uuid.UUID, on: date):
    activity = EXECUTION_ACTIVITY.get(a.activity_type)
    if activity:
        competency.ensure_authorized(ctx, user_id, activity, on=on, gage_type_id=a.gage.gage_type_id,
                                     plant_id=a.plant_id)


# Block manual status changes of a gage while a calibration activity holds it.
def _guard(ctx: TenantContext, gage: Gage, target: ControlStatus) -> None:
    if gage.control_status != ControlStatus.IN_CALIBRATION.value:
        return
    holder = ctx.db.scalar(select(CalibrationActivity.calibration_code).where(
        CalibrationActivity.gage_id == gage.id, CalibrationActivity.status.in_(HOLDING_GAGE),
        CalibrationActivity.activity_type.in_(CALIBRATION_TYPES)))
    if holder:
        raise ConflictError(f"The gage is held by calibration {holder}; complete or cancel it instead",
                            code="calibration_in_progress", details={"calibration": holder})


gages.release_guards.append(_guard)


# ---------------------------------------------------------------- planning


def create(ctx: TenantContext, data: dict) -> CalibrationActivity:
    gage = gages.get_gage(ctx, data["gage_id"], for_update=True)
    if gage.control_status == ControlStatus.INACTIVE.value:
        raise ConflictError("Retired gages cannot be calibrated", code="gage_inactive")
    if not effective_settings(ctx, gage.plant_id)[data["activity_type"]]["enabled"]:
        raise BusinessRuleError(f"{data['activity_type']} is not enabled for this plant", code="activity_type_disabled")
    if data["activity_type"] in CALIBRATION_TYPES:
        open_code = ctx.db.scalar(select(CalibrationActivity.calibration_code).where(
            CalibrationActivity.gage_id == gage.id, CalibrationActivity.status.in_(OPEN),
            CalibrationActivity.activity_type.in_(CALIBRATION_TYPES)))
        if open_code:
            raise ConflictError(f"The gage already has an open calibration ({open_code})",
                                code="open_calibration_exists", details={"calibration": open_code})
    if data.get("technician_id"):
        gages.ensure_active_member(ctx, data["technician_id"], "invalid_technician")
    a = CalibrationActivity(
        organization_id=ctx.organization_id, plant_id=gage.plant_id, gage_id=gage.id, status="PLANNED",
        calibration_code=next_code(ctx.db, ctx.organization_id, "CAL", ctx.today().year), created_by=ctx.user_id,
        **{k: v for k, v in data.items() if k != "gage_id"},
    )
    ctx.db.add(a)
    ctx.db.flush()
    ctx.db.add(CalibrationStatusHistory(organization_id=ctx.organization_id, calibration_id=a.id, to_status="PLANNED",
                                        changed_by=ctx.user_id, comment="Planned"))
    ctx.audit(action="calibration.planned", entity_type="calibration", entity_id=a.id,
              changes={"calibration_code": a.calibration_code, "gage": gage.gage_code, "type": a.activity_type,
                       "planned_date": a.planned_date.isoformat()})
    ctx.audit(action="gage.calibration_planned", entity_type="gage", entity_id=gage.id,
              changes={"calibration_code": a.calibration_code, "type": a.activity_type})
    ctx.db.commit()
    return get_activity(ctx, a.id)


PLAN_FIELDS = {"planned_date", "scheduled_date", "provider_name", "provider_accreditation", "technician_id", "method"}
EXEC_FIELDS = {"performed_date", "method", "environment_temperature", "environment_humidity", "environment_notes",
               "uncertainty", "adjusted", "declared_result", "observations", "provider_name",
               "provider_accreditation"}


def update(ctx: TenantContext, activity_id: uuid.UUID, data: dict) -> CalibrationActivity:
    a = get_activity(ctx, activity_id, for_update=True)
    if a.status in PRE_EXECUTION:
        allowed, perm = PLAN_FIELDS, P.CALIBRATION_MANAGE
    elif a.status == "IN_PROGRESS":
        allowed, perm = EXEC_FIELDS, P.CALIBRATION_EXECUTE
    else:
        raise ConflictError("The activity can no longer be edited", code="activity_locked", details={"status": a.status})
    ctx.ensure(perm)
    bad = sorted(set(data) - allowed)
    if bad:
        raise BusinessRuleError("Fields not editable in this status", code="field_not_editable", details=bad)
    if data.get("performed_date") and data["performed_date"] > ctx.today():
        raise BusinessRuleError("performed_date cannot be in the future", code="future_date")
    if data.get("technician_id"):
        gages.ensure_active_member(ctx, data["technician_id"], "invalid_technician")
        _check_execution_authorization(ctx, a, data["technician_id"], a.scheduled_date or a.planned_date)
    before = audit.snapshot(a, list(data))
    for k, v in data.items():
        setattr(a, k, v)
    ctx.audit(action="calibration.updated", entity_type="calibration", entity_id=a.id,
              changes=audit.diff(before, audit.snapshot(a, list(data))))
    ctx.db.commit()
    return get_activity(ctx, a.id)


def request(ctx: TenantContext, activity_id: uuid.UUID, comment: str | None) -> CalibrationActivity:
    a = get_activity(ctx, activity_id, for_update=True)
    _require_status(a, "PLANNED")
    a.requested_at, a.requested_by = datetime.now(UTC), ctx.user_id
    _move(ctx, a, "REQUESTED", comment)
    ctx.db.commit()
    return a


def schedule(ctx: TenantContext, activity_id: uuid.UUID, data: dict) -> CalibrationActivity:
    a = get_activity(ctx, activity_id, for_update=True)
    _require_status(a, "REQUESTED", "SCHEDULED")
    for k in ("scheduled_date", "provider_name", "provider_accreditation", "technician_id"):
        if data.get(k) is not None:
            setattr(a, k, data[k])
    if a.activity_type == "EXTERNAL_CALIBRATION" and not a.provider_name:
        raise BusinessRuleError("External calibrations need the provider / laboratory", code="provider_required")
    if a.activity_type in EXECUTION_ACTIVITY:
        if not a.technician_id:
            raise BusinessRuleError("Assign the technician who will perform the activity", code="technician_required")
        gages.ensure_active_member(ctx, a.technician_id, "invalid_technician")
        _check_execution_authorization(ctx, a, a.technician_id, a.scheduled_date)
    _move(ctx, a, "SCHEDULED", data.get("comment"),
          {"scheduled_date": a.scheduled_date.isoformat(), "technician_id": str(a.technician_id) if a.technician_id else None,
           "provider": a.provider_name})
    ctx.db.commit()
    return a


# ---------------------------------------------------------------- execution


def start(ctx: TenantContext, activity_id: uuid.UUID) -> CalibrationActivity:
    a = get_activity(ctx, activity_id, for_update=True)
    _require_status(a, "SCHEDULED")
    if a.activity_type in EXECUTION_ACTIVITY:
        if a.technician_id != ctx.user_id:
            raise PermissionDeniedError("Only the assigned technician can start this activity",
                                        code="not_assigned_technician")
        _check_execution_authorization(ctx, a, ctx.user_id, ctx.today())
    elif a.technician_id is None:
        a.technician_id = ctx.user_id
    gage = gages.get_gage(ctx, a.gage_id, for_update=True)
    if gage.control_status == ControlStatus.INACTIVE.value:
        raise ConflictError("Retired gages cannot be calibrated", code="gage_inactive")
    a.started_at = datetime.now(UTC)
    if a.activity_type in CALIBRATION_TYPES and gage.control_status != ControlStatus.IN_CALIBRATION.value:
        a.gage_prior_control_status = gage.control_status
        gages.apply_control_status(ctx, gage, ControlStatus.IN_CALIBRATION,
                                   f"Calibration {a.calibration_code} started", "gage.sent_to_calibration",
                                   {"calibration_code": a.calibration_code})
    _move(ctx, a, "IN_PROGRESS")
    ctx.db.commit()
    return a


def add_point(ctx: TenantContext, activity_id: uuid.UUID, data: dict) -> CalibrationPoint:
    a = get_activity(ctx, activity_id, for_update=True)
    _require_status(a, "IN_PROGRESS")
    if data["lower_limit"] > data["upper_limit"]:
        raise BusinessRuleError("lower_limit must be <= upper_limit", code="invalid_limits")
    if data["phase"] == "AS_LEFT" and not a.adjusted:
        raise BusinessRuleError("As Left results are recorded after an adjustment; mark the activity as adjusted",
                                code="as_left_without_adjustment")
    supersedes = None
    if data.get("supersedes_id"):
        supersedes = ctx.db.scalar(select(CalibrationPoint).where(
            CalibrationPoint.id == data["supersedes_id"], CalibrationPoint.calibration_id == a.id).with_for_update())
        if supersedes is None:
            raise NotFoundError("Point to correct not found")
        if supersedes.superseded:
            raise ConflictError("That point was already corrected", code="already_superseded")
        if not data.get("correction_reason"):
            raise BusinessRuleError("A correction needs a reason", code="reason_required")
        if supersedes.phase != data["phase"]:
            raise BusinessRuleError("A correction must keep the same phase", code="phase_mismatch")
        supersedes.superseded = True
        seq = supersedes.sequence
    else:
        seq = (ctx.db.scalar(select(func.max(CalibrationPoint.sequence)).where(
            CalibrationPoint.calibration_id == a.id, CalibrationPoint.phase == data["phase"])) or 0) + 1
    p = CalibrationPoint(
        organization_id=ctx.organization_id, calibration_id=a.id, sequence=seq, recorded_by=ctx.user_id,
        in_tolerance=data["lower_limit"] <= data["measured"] <= data["upper_limit"], **data,
    )
    ctx.db.add(p)
    ctx.db.flush()
    ctx.audit(action="calibration.point_corrected" if supersedes else "calibration.point_recorded",
              entity_type="calibration", entity_id=a.id, reason=data.get("correction_reason"),
              changes={"phase": p.phase, "sequence": seq, "nominal": audit.plain(p.nominal),
                       "measured": audit.plain(p.measured), "in_tolerance": p.in_tolerance,
                       "supersedes": str(supersedes.id) if supersedes else None,
                       "previous_measured": audit.plain(supersedes.measured) if supersedes else None})
    ctx.db.commit()
    return p


def add_standard(ctx: TenantContext, activity_id: uuid.UUID, standard_id: uuid.UUID,
                 exception_reason: str | None) -> CalibrationStandardUsage:
    a = get_activity(ctx, activity_id, for_update=True)
    _require_status(a, "IN_PROGRESS")
    on = a.performed_date or ctx.today()
    snap = standards.check_usable(ctx, standard_id, on, exception_reason)
    if ctx.db.scalar(select(CalibrationStandardUsage.id).where(CalibrationStandardUsage.calibration_id == a.id,
                                                               CalibrationStandardUsage.standard_id == standard_id)):
        raise ConflictError("Standard already recorded for this activity", code="duplicate_standard")
    u = CalibrationStandardUsage(
        organization_id=ctx.organization_id, calibration_id=a.id, standard_id=standard_id, used_on=on,
        standard_status=snap["status"], certificate_id=snap["certificate_id"],
        valid_until=date.fromisoformat(snap["valid_until"]) if snap["valid_until"] else None,
        is_exception=snap["exception"], exception_reason=exception_reason if snap["exception"] else None,
        exception_authorized_by=ctx.user_id if snap["exception"] else None, recorded_by=ctx.user_id,
    )
    ctx.db.add(u)
    ctx.db.flush()
    ctx.audit(action="calibration.standard_used", entity_type="calibration", entity_id=a.id,
              reason=exception_reason if snap["exception"] else None, changes=snap | {"used_on": on.isoformat()})
    if snap["exception"]:
        ctx.audit(action="standard.used_under_exception", entity_type="standard", entity_id=standard_id,
                  reason=exception_reason, changes={"calibration_code": a.calibration_code, "status": snap["status"]})
    ctx.db.commit()
    return u


def remove_standard(ctx: TenantContext, activity_id: uuid.UUID, usage_id: uuid.UUID, reason: str) -> None:
    a = get_activity(ctx, activity_id, for_update=True)
    _require_status(a, "IN_PROGRESS")
    u = ctx.db.scalar(select(CalibrationStandardUsage).where(CalibrationStandardUsage.id == usage_id,
                                                             CalibrationStandardUsage.calibration_id == a.id))
    if u is None:
        raise NotFoundError("Standard usage not found")
    ctx.audit(action="calibration.standard_removed", entity_type="calibration", entity_id=a.id, reason=reason,
              changes={"standard_id": str(u.standard_id)})
    ctx.db.delete(u)
    ctx.db.commit()


def add_certificate(ctx: TenantContext, activity_id: uuid.UUID, meta: dict, filename: str, data: bytes,
                    reason: str | None) -> CalibrationCertificate:
    a = get_activity(ctx, activity_id, for_update=True)
    if a.status in ("PLANNED", "REQUESTED", "SCHEDULED", "CANCELLED"):
        raise ConflictError("Certificates are attached once the activity has started", code="invalid_activity_status")
    approved = a.status in ("APPROVED", "RELEASED")
    if a.status in ("PENDING_REVIEW", "PENDING_APPROVAL"):
        raise ConflictError("The activity is under review; return it to add evidence", code="activity_locked")
    current = ctx.db.scalar(select(CalibrationCertificate).where(
        CalibrationCertificate.calibration_id == a.id, CalibrationCertificate.status == "CURRENT"))
    if approved:
        # Never silently replace an approved certificate.
        ctx.ensure(P.CALIBRATION_RELEASE)
        if not reason:
            raise BusinessRuleError("Replacing a certificate of an approved activity needs a reason",
                                    code="reason_required")
    if meta["issue_date"] > ctx.today():
        raise BusinessRuleError("issue_date cannot be in the future", code="future_date")
    att = documents.store(ctx, entity_type="calibration", entity_id=a.id, category="CERTIFICATE", filename=filename,
                          data=data, title=meta["certificate_number"], pdf_only=True, locked=approved)
    if current:
        current.status = "SUPERSEDED"
        current.superseded_reason = reason or "Replaced before approval"
    cert = CalibrationCertificate(organization_id=ctx.organization_id, calibration_id=a.id, gage_id=a.gage_id,
                                  attachment_id=att.id, uploaded_by=ctx.user_id,
                                  certificate_number=meta["certificate_number"].strip(),
                                  issuer=meta["issuer"].strip(), issue_date=meta["issue_date"])
    ctx.db.add(cert)
    ctx.db.flush()
    ctx.audit(action="calibration.certificate_replaced" if current else "calibration.certificate_added",
              entity_type="calibration", entity_id=a.id, reason=reason,
              changes={"certificate": cert.certificate_number,
                       "superseded": current.certificate_number if current else None})
    ctx.db.commit()
    return cert


def compute_outcome(a: CalibrationActivity, points: list[CalibrationPoint]) -> tuple[str | None, bool | None, bool | None]:
    found = [p for p in points if p.phase == "AS_FOUND"]
    left = [p for p in points if p.phase == "AS_LEFT"]
    found_ok = all(p.in_tolerance for p in found) if found else None
    left_ok = all(p.in_tolerance for p in left) if left else None
    if not found and not left:
        return a.declared_result, None, None
    if a.adjusted:
        if left_ok:
            return ("PASS" if found_ok else "PASS_AFTER_ADJUSTMENT"), found_ok, left_ok
        return "FAIL", found_ok, left_ok
    return ("PASS" if found_ok else "FAIL"), found_ok, left_ok


def missing_requirements(ctx: TenantContext, a: CalibrationActivity) -> list[str]:
    """Evidence/data still missing for submission, according to the configuration."""
    cfg = _setting(ctx, a)
    points = current_points(ctx, a)
    missing = []
    if not a.performed_date:
        missing.append("performed_date")
    if a.activity_type in EXECUTION_ACTIVITY and not a.method:
        missing.append("method")
    if cfg["require_as_found"] and not any(p.phase == "AS_FOUND" for p in points):
        missing.append("as_found_points")
    if a.adjusted and not any(p.phase == "AS_LEFT" for p in points):
        missing.append("as_left_points")
    if cfg["require_standard"] and not ctx.db.scalar(select(CalibrationStandardUsage.id).where(
            CalibrationStandardUsage.calibration_id == a.id)):
        missing.append("standard")
    if cfg["require_certificate"] and not ctx.db.scalar(select(CalibrationCertificate.id).where(
            CalibrationCertificate.calibration_id == a.id, CalibrationCertificate.status == "CURRENT")):
        missing.append("certificate")
    if cfg["require_environment"] and a.environment_temperature is None:
        missing.append("environment_temperature")
    if not points and not a.declared_result:
        missing.append("result")
    return missing


def submit(ctx: TenantContext, activity_id: uuid.UUID, comment: str | None) -> CalibrationActivity:
    a = get_activity(ctx, activity_id, for_update=True)
    _require_status(a, "IN_PROGRESS")
    missing = missing_requirements(ctx, a)
    if missing:
        raise BusinessRuleError("The activity is incomplete", code="incomplete_activity", details=missing)
    if a.activity_type in EXECUTION_ACTIVITY:
        _check_execution_authorization(ctx, a, a.technician_id, a.performed_date)
    a.result, a.as_found_in_tolerance, a.as_left_in_tolerance = compute_outcome(a, current_points(ctx, a))
    a.submitted_at, a.submitted_by = datetime.now(UTC), ctx.user_id
    _move(ctx, a, "PENDING_REVIEW", comment, {"result": a.result})
    reviewers = [u.id for u in competency.authorized_users(ctx, "TECHNICAL_REVIEW", a.gage.gage_type_id, a.plant_id)]
    notify(ctx, reviewers, "calibration.submitted", f"{a.calibration_code} awaiting technical review",
           f"{a.gage.gage_code} · {a.activity_type} · {a.result}", f"/calibrations/{a.id}")
    ctx.db.commit()
    return a


def _distinct_people(a: CalibrationActivity, user_id: uuid.UUID, role: str) -> None:
    if user_id in (a.technician_id, a.submitted_by):
        raise BusinessRuleError(f"The {role} cannot be the person who performed the activity",
                                code="segregation_of_duties")
    if role == "approver" and user_id == a.reviewer_id:
        raise BusinessRuleError("The approver must be different from the technical reviewer",
                                code="segregation_of_duties")


def review(ctx: TenantContext, activity_id: uuid.UUID, accept: bool, comments: str | None) -> CalibrationActivity:
    a = get_activity(ctx, activity_id, for_update=True)
    _require_status(a, "PENDING_REVIEW")
    _distinct_people(a, ctx.user_id, "reviewer")
    competency.ensure_authorized(ctx, ctx.user_id, "TECHNICAL_REVIEW", gage_type_id=a.gage.gage_type_id,
                                 plant_id=a.plant_id)
    if not accept:
        if not comments:
            raise BusinessRuleError("Explain why the activity is returned", code="reason_required")
        _move(ctx, a, "IN_PROGRESS", comments, {"review": "returned"})
        notify(ctx, [a.technician_id, a.submitted_by], "calibration.returned",
               f"{a.calibration_code} returned by technical review", comments, f"/calibrations/{a.id}")
    else:
        a.reviewer_id, a.reviewed_at, a.review_comments = ctx.user_id, datetime.now(UTC), comments
        _move(ctx, a, "PENDING_APPROVAL", comments, {"review": "accepted"})
        approvers = [u.id for u in competency.authorized_users(ctx, "APPROVAL", a.gage.gage_type_id, a.plant_id)]
        notify(ctx, approvers, "calibration.reviewed", f"{a.calibration_code} awaiting approval",
               f"{a.gage.gage_code} · {a.result}", f"/calibrations/{a.id}")
    ctx.db.commit()
    return a


def approve(ctx: TenantContext, activity_id: uuid.UUID, accept: bool, comments: str | None) -> CalibrationActivity:
    a = get_activity(ctx, activity_id, for_update=True)
    _require_status(a, "PENDING_APPROVAL")
    _distinct_people(a, ctx.user_id, "approver")
    competency.ensure_authorized(ctx, ctx.user_id, "APPROVAL", gage_type_id=a.gage.gage_type_id, plant_id=a.plant_id)
    if not accept:
        if not comments:
            raise BusinessRuleError("Explain why the activity is rejected", code="reason_required")
        a.reviewer_id = a.reviewed_at = None
        _move(ctx, a, "IN_PROGRESS", comments, {"approval": "returned"})
        notify(ctx, [a.technician_id, a.submitted_by], "calibration.returned",
               f"{a.calibration_code} returned at approval", comments, f"/calibrations/{a.id}")
    else:
        a.approver_id, a.approved_at = ctx.user_id, datetime.now(UTC)
        _move(ctx, a, "APPROVED", comments)
    ctx.db.commit()
    return a


def release(ctx: TenantContext, activity_id: uuid.UUID, comment: str | None) -> CalibrationActivity:
    """Release an approved activity and update the gage in the same transaction."""
    a = get_activity(ctx, activity_id, for_update=True)
    _require_status(a, "APPROVED")
    gage = gages.get_gage(ctx, a.gage_id, for_update=True)
    missing = missing_requirements(ctx, a)  # configuration may have changed since submission
    if missing:
        raise BusinessRuleError("Required evidence is missing", code="incomplete_activity", details=missing)

    gage_changes: dict = {}
    if a.activity_type in CALIBRATION_TYPES:
        gage_changes = gages.record_calibration(ctx, gage, a.performed_date)
        a.due_date = a.performed_date + timedelta(days=gage.calibration_frequency_days)
    else:
        if gage.last_verification_date is None or a.performed_date >= gage.last_verification_date:
            gage_changes = {"last_verification_date": [audit.plain(gage.last_verification_date),
                                                       a.performed_date.isoformat()]}
            gage.last_verification_date = a.performed_date

    reason = f"{a.calibration_code} released · result {a.result}"
    if a.result == "FAIL":
        if gage.control_status != ControlStatus.OUT_OF_SERVICE.value:
            gages.apply_control_status(ctx, gage, ControlStatus.OUT_OF_SERVICE, reason, "gage.restricted",
                                       {"calibration_code": a.calibration_code} | gage_changes)
    elif gage.control_status == ControlStatus.IN_CALIBRATION.value:
        gages.apply_control_status(ctx, gage, ControlStatus.ACTIVE, reason, "gage.released",
                                   {"calibration_code": a.calibration_code} | gage_changes)
    elif gage_changes:
        ctx.audit(action="gage.calibration_recorded", entity_type="gage", entity_id=gage.id, reason=reason,
                  changes=gage_changes | {"calibration_code": a.calibration_code})

    # Evidence of a released record can no longer be withdrawn.
    for att in ctx.db.scalars(select(Attachment).where(Attachment.entity_type == "calibration",
                                                       Attachment.entity_id == a.id, Attachment.removed_at.is_(None))):
        documents.lock(att)
    a.released_by, a.released_at = ctx.user_id, datetime.now(UTC)
    _move(ctx, a, "RELEASED", comment, {"result": a.result, "due_date": a.due_date.isoformat() if a.due_date else None,
                                        "as_found_in_tolerance": a.as_found_in_tolerance})
    notify(ctx, [gage.responsible_user_id], "calibration.released", f"{a.calibration_code} released",
           f"{gage.gage_code} · {a.result}", f"/gages/{gage.id}")
    ctx.db.commit()
    return a


def cancel(ctx: TenantContext, activity_id: uuid.UUID, reason: str) -> CalibrationActivity:
    a = get_activity(ctx, activity_id, for_update=True)
    _require_status(a, "PLANNED", "REQUESTED", "SCHEDULED", "IN_PROGRESS", "PENDING_REVIEW", "PENDING_APPROVAL")
    gage = gages.get_gage(ctx, a.gage_id, for_update=True)
    a.cancel_reason = reason
    if a.gage_prior_control_status and gage.control_status == ControlStatus.IN_CALIBRATION.value:
        gages.apply_control_status(ctx, gage, ControlStatus(a.gage_prior_control_status),
                                   f"{a.calibration_code} cancelled: {reason}", "gage.calibration_cancelled",
                                   {"calibration_code": a.calibration_code})
    _move(ctx, a, "CANCELLED", reason)
    ctx.db.commit()
    return a


# ---------------------------------------------------------------- queries


def list_activities(ctx: TenantContext, *, gage_id=None, status=None, activity_type=None, q=None,
                    page=1, page_size=50) -> tuple[list[CalibrationActivity], int]:
    stmt = select(CalibrationActivity).join(Gage, Gage.id == CalibrationActivity.gage_id).where(
        CalibrationActivity.organization_id == ctx.organization_id)
    if ctx.plant_ids is not None:
        stmt = stmt.where(CalibrationActivity.plant_id.in_(ctx.plant_ids))
    if gage_id:
        stmt = stmt.where(CalibrationActivity.gage_id == gage_id)
    if status:
        stmt = stmt.where(CalibrationActivity.status.in_(status))
    if activity_type:
        stmt = stmt.where(CalibrationActivity.activity_type == activity_type)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(CalibrationActivity.calibration_code.ilike(like) | Gage.gage_code.ilike(like)
                          | CalibrationActivity.provider_name.ilike(like))
    total = ctx.db.scalar(select(func.count()).select_from(stmt.with_only_columns(CalibrationActivity.id).subquery()))
    rows = ctx.db.scalars(stmt.order_by(CalibrationActivity.created_at.desc())
                          .limit(page_size).offset((page - 1) * page_size)).unique()
    return list(rows), total


def overview(ctx: TenantContext) -> dict:
    counts = dict(ctx.db.execute(
        select(CalibrationActivity.status, func.count())
        .where(CalibrationActivity.organization_id == ctx.organization_id,
               *( [CalibrationActivity.plant_id.in_(ctx.plant_ids)] if ctx.plant_ids is not None else []))
        .group_by(CalibrationActivity.status)).all())
    gage_counts = gages.status_counts(ctx)
    horizon = ctx.today() + timedelta(days=ctx.organization.due_soon_days)
    open_ids = select(CalibrationActivity.gage_id).where(CalibrationActivity.status.in_(OPEN),
                                                         CalibrationActivity.activity_type.in_(CALIBRATION_TYPES))
    unplanned = list(ctx.db.scalars(
        gages.scoped_query(ctx).where(Gage.control_status == "ACTIVE",
                                      (Gage.next_due_date.is_(None)) | (Gage.next_due_date <= horizon),
                                      Gage.id.not_in(open_ids))
        .order_by(Gage.next_due_date.asc().nulls_first()).limit(20)).unique())
    return {
        "as_of": ctx.today().isoformat(),
        "gages_overdue": gage_counts["OVERDUE"],
        "gages_due_soon": gage_counts["DUE_SOON"],
        "gages_in_calibration": gage_counts["IN_CALIBRATION"],
        "pending": sum(counts.get(s, 0) for s in PRE_EXECUTION),
        "in_progress": counts.get("IN_PROGRESS", 0),
        "pending_review": counts.get("PENDING_REVIEW", 0),
        "pending_approval": counts.get("PENDING_APPROVAL", 0),
        "pending_release": counts.get("APPROVED", 0),
        "by_status": counts,
        "unplanned_due": [gages.to_out(ctx, g) for g in unplanned],
    }


def calendar(ctx: TenantContext, start: date, end: date) -> list[dict]:
    if (end - start).days > 120:
        raise BusinessRuleError("Calendar range is limited to 120 days", code="range_too_large")
    events = []
    acts, _ = list_activities(ctx, page_size=10_000)
    for a in acts:
        if a.status == "CANCELLED":
            continue
        d = a.performed_date if a.status == "RELEASED" else (a.scheduled_date or a.planned_date)
        if d and start <= d <= end:
            events.append({"date": d.isoformat(), "kind": "activity", "id": str(a.id), "code": a.calibration_code,
                           "gage_id": str(a.gage_id), "gage_code": a.gage.gage_code, "activity_type": a.activity_type,
                           "status": a.status})
    for g in ctx.db.scalars(gages.scoped_query(ctx).where(Gage.control_status != "INACTIVE",
                                                          Gage.next_due_date >= start, Gage.next_due_date <= end)).unique():
        events.append({"date": g.next_due_date.isoformat(), "kind": "due", "gage_id": str(g.id),
                       "gage_code": g.gage_code, "status": gages.current_status(ctx, g).value})
    return sorted(events, key=lambda e: (e["date"], e["kind"]))


def standard_usages(ctx: TenantContext, standard_id: uuid.UUID) -> list[tuple]:
    standards.get_standard(ctx, standard_id)
    return list(ctx.db.execute(
        select(CalibrationStandardUsage, CalibrationActivity)
        .join(CalibrationActivity, CalibrationActivity.id == CalibrationStandardUsage.calibration_id)
        .where(CalibrationStandardUsage.standard_id == standard_id,
               CalibrationStandardUsage.organization_id == ctx.organization_id)
        .order_by(CalibrationStandardUsage.used_on.desc())).unique())
