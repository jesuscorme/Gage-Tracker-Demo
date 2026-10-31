"""MSA studies: configuration, data capture, calculation, criteria, decision and reports."""

import random
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select

from app import engine
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.sequences import next_code
from app.modules.audit import service as audit
from app.modules.competency import service as competency
from app.modules.configuration import service as config
from app.modules.configuration import workflow
from app.modules.events import service as events
from app.modules.gages import service as gages
from app.modules.gages.models import Gage
from app.modules.gages.status import GageStatus
from app.modules.identity.deps import TenantContext
from app.modules.identity.permissions import P
from app.modules.msa.models import DECISIONS, MsaCriteriaSet, MsaObservation, MsaReport, MsaRun, MsaStudy
from app.modules.notifications.service import notify
from app.modules.organizations.router import get_plant

ENTITY = "msa_study"
STUDY_FIELDS = ["title", "method", "characteristic", "part_number", "part_revision", "customer", "gage_id",
                "responsible_id", "plant_id", "department_id", "start_date", "end_date", "design", "params",
                "criteria_set_id", "notes"]
# Observation fields required per method family, and the fields that identify a reading.
FAMILY_REQUIRED = {
    "VARIABLE_GRR": ("operator", "part", "trial", "value"),
    "ATTRIBUTE": ("operator", "part", "trial", "category"),
    "BIAS": ("trial", "value"),
    "TYPE1": ("trial", "value"),
    "LINEARITY": ("part", "reference", "trial", "value"),
    "STABILITY": ("subgroup", "trial", "value"),
}
FAMILY_KEY = {
    "VARIABLE_GRR": ("operator", "part", "trial"), "ATTRIBUTE": ("operator", "part", "trial"),
    "BIAS": ("trial",), "TYPE1": ("trial",), "LINEARITY": ("part", "trial"), "STABILITY": ("subgroup", "trial"),
}
UNUSABLE_GAGE = {GageStatus.OUT_OF_SERVICE, GageStatus.INACTIVE, GageStatus.OVERDUE, GageStatus.IN_CALIBRATION}


def family(method: str) -> str:
    return engine.method(method).family


# ---------------------------------------------------------------- studies

def get_study(ctx: TenantContext, study_id: uuid.UUID, *, for_update: bool = False) -> MsaStudy:
    stmt = select(MsaStudy).where(MsaStudy.id == study_id, MsaStudy.organization_id == ctx.organization_id)
    if for_update:
        stmt = stmt.with_for_update(of=MsaStudy)
    s = ctx.db.scalar(stmt.execution_options(populate_existing=True))
    if s is None or not ctx.can_access_plant(s.plant_id):
        raise NotFoundError("MSA study not found")
    return s


def list_studies(ctx: TenantContext, *, gage_id=None, status=None, method=None, q=None) -> list[MsaStudy]:
    stmt = select(MsaStudy).where(MsaStudy.organization_id == ctx.organization_id)
    if ctx.plant_ids is not None:
        stmt = stmt.where(MsaStudy.plant_id.in_(ctx.plant_ids))
    if gage_id:
        stmt = stmt.where(MsaStudy.gage_id == gage_id)
    if status:
        stmt = stmt.where(MsaStudy.status == status)
    if method:
        stmt = stmt.where(MsaStudy.method == method)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(MsaStudy.study_code.ilike(like), MsaStudy.title.ilike(like),
                              MsaStudy.characteristic.ilike(like), MsaStudy.part_number.ilike(like)))
    return list(ctx.db.scalars(stmt.order_by(MsaStudy.created_at.desc()).limit(500)))


def _design_errors(method: str, design: dict, params: dict) -> list[str]:
    """Checks that do not need data. The engine re-validates everything with the data."""
    fam = family(method)
    errors = []

    def num(name):
        v = design.get(name)
        return None if v in (None, "") else v

    tol, lsl, usl = num("tolerance"), num("lsl"), num("usl")
    if tol is not None and tol <= 0:
        errors.append("tolerance must be positive")
    if lsl is not None and usl is not None and usl <= lsl:
        errors.append("usl must be greater than lsl")
    if num("resolution") is not None and design["resolution"] <= 0:
        errors.append("resolution must be positive")
    if fam == "VARIABLE_GRR":
        for name, minimum in (("operators", 2), ("parts", 2), ("trials", 2), ("parts_per_operator", 2)):
            if num(name) is not None and design[name] < minimum:
                errors.append(f"{name} must be at least {minimum}")
        if method == "GRR_CROSSED_AR":
            if num("operators") is not None and design["operators"] > 3:
                errors.append("Average & Range supports 2 or 3 operators (use ANOVA for more)")
            if num("trials") is not None and design["trials"] > 3:
                errors.append("Average & Range supports 2 or 3 trials (use ANOVA for more)")
            if num("parts") is not None and design["parts"] > 10:
                errors.append("Average & Range supports up to 10 parts (use ANOVA for more)")
        if method == "GRR_NESTED_ANOVA" and num("parts") is not None:
            errors.append("nested designs declare parts_per_operator, not parts")
    if fam == "ATTRIBUTE":
        cats = design.get("categories") or []
        if len(cats) < 2 or len(set(cats)) != len(cats):
            errors.append("declare at least two distinct categories")
        for part, ref in (design.get("part_reference") or {}).items():
            if ref not in cats:
                errors.append(f"reference '{ref}' of part '{part}' is not a category")
        acc, rej = design.get("accept_category"), design.get("reject_category")
        if (acc or rej) and not (acc in cats and rej in cats and acc != rej):
            errors.append("accept_category and reject_category must be two different categories")
    if fam in ("BIAS", "TYPE1") and num("reference") is None:
        errors.append("reference value is required")
    if fam == "TYPE1" and tol is None and (lsl is None or usl is None):
        errors.append("tolerance (or lsl and usl) is required for a Type 1 study")
    if fam == "STABILITY" and not 1 <= int(design.get("subgroup_size") or 1) <= 10:
        errors.append("subgroup_size must be between 1 and 10")
    k = params.get("study_var_multiplier")
    if k is not None and k not in (6, 5.15):
        errors.append("study_var_multiplier must be 6 or 5.15")
    alpha = params.get("alpha")
    if alpha is not None and not 0 < alpha < 1:
        errors.append("alpha must be between 0 and 1")
    if fam == "STABILITY" and params.get("rules"):
        from app.engine.stability import rule_config
        from app.engine.common import Checker
        chk = Checker()
        rule_config(chk, params["rules"])
        errors += [i.message for i in chk.issues]
    return errors


def _check_design(method: str, design: dict, params: dict) -> None:
    errors = _design_errors(method, design, params)
    if errors:
        raise BusinessRuleError("The study configuration is not valid", code="invalid_design", details=errors)


def _check_gage(ctx: TenantContext, gage_id: uuid.UUID) -> Gage:
    gage = gages.get_gage(ctx, gage_id)
    if gages.current_status(ctx, gage) == GageStatus.INACTIVE:
        raise BusinessRuleError("A retired gage cannot be used in an MSA study", code="gage_unavailable")
    return gage


def _check_department(ctx: TenantContext, plant_id: uuid.UUID, department_id: uuid.UUID | None) -> None:
    from app.modules.organizations.models import Department

    if department_id is None:
        return
    d = ctx.db.get(Department, department_id)
    if d is None or d.organization_id != ctx.organization_id or d.plant_id != plant_id:
        raise BusinessRuleError("The department does not belong to the plant", code="invalid_department")


def _check_criteria_choice(ctx: TenantContext, criteria_id, method: str) -> None:
    if criteria_id is None:
        return
    c = get_criteria(ctx, criteria_id)
    if c.status != "APPROVED" or c.method != method:
        raise BusinessRuleError("Only approved criteria for the same method can be selected", code="invalid_criteria")


def create_study(ctx: TenantContext, data: dict, custom_fields: dict | None) -> MsaStudy:
    get_plant(ctx, data["plant_id"])
    gage = _check_gage(ctx, data["gage_id"])
    gages.ensure_active_member(ctx, data["responsible_id"], "invalid_responsible")
    _check_design(data["method"], data["design"], data["params"])
    _check_criteria_choice(ctx, data.get("criteria_set_id"), data["method"])
    _check_department(ctx, data["plant_id"], data.get("department_id"))
    config.apply_values(ctx, ENTITY, None, custom_fields, creating=True)
    version = workflow.version_for_new(ctx, ENTITY)
    study = MsaStudy(organization_id=ctx.organization_id, created_by=ctx.user_id,
                     study_code=next_code(ctx.db, ctx.organization_id, "MSA", data["start_date"].year),
                     workflow_version=version, status=workflow.initial_state(ctx, ENTITY, version), **data)
    ctx.db.add(study)
    ctx.db.flush()
    config.apply_values(ctx, ENTITY, study.id, custom_fields, creating=True)
    ctx.audit(action="msa.study_created", entity_type=ENTITY, entity_id=study.id,
              changes=audit.snapshot(study, STUDY_FIELDS) | {"gage_code": gage.gage_code})
    workflow.record_created(ctx, ENTITY, study, study.id)
    ctx.db.commit()
    return get_study(ctx, study.id)


def update_study(ctx: TenantContext, study_id: uuid.UUID, data: dict) -> MsaStudy:
    study = get_study(ctx, study_id, for_update=True)
    workflow.ensure_capability(ctx, ENTITY, study, "configure")
    before = audit.snapshot(study, STUDY_FIELDS)
    method = data.get("method", study.method)
    if method != study.method and _active_observations(ctx, study):
        raise ConflictError("The method cannot change once data has been captured", code="study_has_data")
    if "gage_id" in data and data["gage_id"] != study.gage_id:
        if _active_observations(ctx, study):
            raise ConflictError("The gage cannot change once data has been captured", code="study_has_data")
        _check_gage(ctx, data["gage_id"])
    if "responsible_id" in data:
        gages.ensure_active_member(ctx, data["responsible_id"], "invalid_responsible")
    if "plant_id" in data:
        get_plant(ctx, data["plant_id"])
    _check_design(method, data.get("design", study.design), data.get("params", study.params))
    _check_criteria_choice(ctx, data.get("criteria_set_id", study.criteria_set_id), method)
    _check_department(ctx, data.get("plant_id", study.plant_id), data.get("department_id", study.department_id))
    for k, v in data.items():
        setattr(study, k, v)
    changes = audit.diff(before, audit.snapshot(study, STUDY_FIELDS))
    if changes:
        ctx.audit(action="msa.study_updated", entity_type=ENTITY, entity_id=study.id, changes=changes)
    ctx.db.commit()
    return get_study(ctx, study.id)


# ---------------------------------------------------------------- observations

def _active_observations(ctx: TenantContext, study: MsaStudy) -> list[MsaObservation]:
    return list(ctx.db.scalars(select(MsaObservation).where(
        MsaObservation.study_id == study.id, MsaObservation.superseded.is_(False),
        MsaObservation.organization_id == ctx.organization_id)
        .order_by(MsaObservation.recorded_at, MsaObservation.id)))


def observations(ctx: TenantContext, study_id: uuid.UUID, include_superseded: bool) -> list[MsaObservation]:
    study = get_study(ctx, study_id)
    stmt = select(MsaObservation).where(MsaObservation.study_id == study.id)
    if not include_superseded:
        stmt = stmt.where(MsaObservation.superseded.is_(False))
    return list(ctx.db.scalars(stmt.order_by(MsaObservation.recorded_at, MsaObservation.id)))


def _ensure_gage_usable(ctx: TenantContext, study: MsaStudy) -> None:
    gage = gages.get_gage(ctx, study.gage_id)
    status = gages.current_status(ctx, gage)
    if status in UNUSABLE_GAGE:
        raise BusinessRuleError(f"Gage {gage.gage_code} is {status.value}; data cannot be captured with it",
                                code="gage_unavailable", details={"gage_status": status.value})


def _row_key(fam: str, row: dict) -> tuple:
    return tuple(str(row.get(k)).strip().upper() if k in ("operator", "part") else row.get(k)
                 for k in FAMILY_KEY[fam])


def _normalize_row(fam: str, row: dict, i: int, errors: list) -> dict | None:
    out = {}
    for k in FAMILY_REQUIRED[fam]:
        if row.get(k) in (None, ""):
            errors.append({"row": i, "field": k, "message": f"'{k}' is required"})
    if any(e["row"] == i for e in errors):
        return None
    for k in ("operator", "part", "category"):
        if row.get(k) not in (None, ""):
            out[k] = str(row[k]).strip()[:60]
    for k in ("trial", "subgroup"):
        if row.get(k) not in (None, ""):
            try:
                v = int(row[k])
                if v < 1 or float(row[k]) != v:
                    raise ValueError
                out[k] = v
            except (TypeError, ValueError):
                errors.append({"row": i, "field": k, "message": f"'{k}' must be a positive integer"})
    for k in ("value", "reference"):
        if row.get(k) not in (None, ""):
            try:
                d = Decimal(str(row[k]).strip().replace(",", ".") if isinstance(row[k], str) else str(row[k]))
                if not d.is_finite():
                    raise ValueError
                out[k] = d
            except Exception:
                errors.append({"row": i, "field": k, "message": f"'{k}' must be a number"})
    if row.get("measured_at") not in (None, ""):
        try:
            out["measured_at"] = row["measured_at"] if isinstance(row["measured_at"], datetime) else \
                datetime.fromisoformat(str(row["measured_at"]))
        except ValueError:
            errors.append({"row": i, "field": "measured_at", "message": "measured_at must be an ISO date-time"})
    if fam == "ATTRIBUTE" and "value" in out:
        errors.append({"row": i, "field": "value", "message": "attribute studies capture 'category', not numbers"})
    return out


def build_observations(ctx: TenantContext, study: MsaStudy, rows: list[dict], *, source: str = "MANUAL",
                       import_job_id: uuid.UUID | None = None, extra: dict | None = None) -> list[MsaObservation]:
    """Validate a batch and add it to the session (no commit). All rows or none."""
    workflow.ensure_capability(ctx, ENTITY, study, "capture")
    _ensure_gage_usable(ctx, study)
    fam = family(study.method)
    if not rows:
        raise BusinessRuleError("No observations were provided", code="no_data")
    errors: list[dict] = []
    normalized = [_normalize_row(fam, r, i, errors) for i, r in enumerate(rows, start=1)]
    existing = {_row_key(fam, {k: getattr(o, k) for k in FAMILY_KEY[fam]}) for o in _active_observations(ctx, study)}
    cats = study.design.get("categories") or []
    seen: dict[tuple, int] = {}
    for i, n in enumerate(normalized, start=1):
        if n is None or any(e["row"] == i for e in errors):
            continue
        key = _row_key(fam, n)
        if key in existing:
            errors.append({"row": i, "message": f"duplicate of an existing observation {dict(zip(FAMILY_KEY[fam], key))}"})
        elif key in seen:
            errors.append({"row": i, "message": f"duplicate of row {seen[key]} in this batch"})
        seen.setdefault(key, i)
        if fam == "ATTRIBUTE" and cats and n.get("category") not in cats:
            errors.append({"row": i, "field": "category", "message": f"'{n.get('category')}' is not a declared category"})
    if errors:
        raise BusinessRuleError("Observations are not valid; nothing was saved", code="invalid_observations",
                                details=errors[:200])
    out = []
    for n in normalized:
        o = MsaObservation(organization_id=ctx.organization_id, study_id=study.id, source=source,
                           import_job_id=import_job_id, recorded_by=ctx.user_id, **n, **(extra or {}))
        ctx.db.add(o)
        out.append(o)
    ctx.db.flush()
    ctx.audit(action="msa.observations_added", entity_type=ENTITY, entity_id=study.id,
              changes={"count": len(out), "source": source})
    return out


def add_observations(ctx: TenantContext, study_id: uuid.UUID, rows: list[dict]) -> list[MsaObservation]:
    study = get_study(ctx, study_id, for_update=True)
    out = build_observations(ctx, study, rows)
    ctx.db.commit()
    return out


def correct_observation(ctx: TenantContext, obs_id: uuid.UUID, row: dict | None, reason: str) -> MsaObservation | None:
    """Supersede a reading with a corrected one (``row``) or void it (``row`` is None)."""
    original = ctx.db.scalar(select(MsaObservation).where(
        MsaObservation.id == obs_id, MsaObservation.organization_id == ctx.organization_id).with_for_update())
    if original is None:
        raise NotFoundError("Observation not found")
    study = get_study(ctx, original.study_id, for_update=True)
    workflow.ensure_capability(ctx, ENTITY, study, "capture")
    if original.superseded:
        raise ConflictError("This observation was already corrected", code="already_superseded")
    original.superseded = True
    ctx.db.flush()
    replacement = None
    if row is not None:
        merged = {k: getattr(original, k) for k in ("operator", "part", "trial", "subgroup", "value", "category",
                                                   "reference", "measured_at")} | row
        replacement = build_observations(ctx, study, [merged], source=original.source,
                                         extra={"supersedes_id": original.id, "correction_reason": reason})[0]
    ctx.audit(action="msa.observation_corrected" if row else "msa.observation_voided", entity_type=ENTITY,
              entity_id=study.id, reason=reason,
              changes={"observation": str(original.id),
                       "before": {k: audit.plain(getattr(original, k)) for k in ("operator", "part", "trial",
                                                                                 "subgroup", "value", "category")},
                       "after": row and {k: audit.plain(v) for k, v in row.items()}})
    ctx.db.commit()
    return replacement


def run_order(study: MsaStudy) -> list[dict]:
    """Randomized measurement sequence for crossed/attribute designs (reproducible per study)."""
    d = study.design
    if family(study.method) not in ("VARIABLE_GRR", "ATTRIBUTE") or study.method == "GRR_NESTED_ANOVA":
        return []
    ops = d.get("operator_names") or [f"O{i}" for i in range(1, int(d.get("operators") or 0) + 1)]
    parts = d.get("part_ids") or [str(i) for i in range(1, int(d.get("parts") or 0) + 1)]
    trials = int(d.get("trials") or 0)
    rng = random.Random(study.id.int)
    plan = []
    for t in range(1, trials + 1):
        for op in ops:
            order = parts[:] if d.get("sequence") == "SEQUENTIAL" else rng.sample(parts, len(parts))
            plan += [{"trial": t, "operator": op, "part": p} for p in order]
    return [dict(step=i + 1, **p) for i, p in enumerate(plan)]


# ---------------------------------------------------------------- calculation

def engine_input(study: MsaStudy, rows: list[MsaObservation]) -> dict:
    fam = family(study.method)
    obs = []
    for o in rows:
        value = o.category if fam == "ATTRIBUTE" else (float(o.value) if o.value is not None else None)
        item = {"value": value}
        for k in ("operator", "part", "trial", "subgroup"):
            if getattr(o, k) is not None:
                item[k] = getattr(o, k)
        if o.reference is not None:
            item["reference"] = float(o.reference)
        if o.measured_at is not None:
            item["measured_at"] = o.measured_at.isoformat()
        obs.append(item)
    obs.sort(key=lambda x: engine.canonical(x))
    design = {k: v for k, v in study.design.items() if v not in (None, "", [])}
    if fam == "ATTRIBUTE" and design.get("part_reference"):
        design["reference"] = design.pop("part_reference")
    if study.method == "GRR_NESTED_ANOVA":
        design.pop("parts", None)
    return {"design": design, "observations": obs, "params": dict(study.params or {})}


def validate_data(ctx: TenantContext, study_id: uuid.UUID) -> dict:
    study = get_study(ctx, study_id)
    rows = _active_observations(ctx, study)
    issues = [{"code": "invalid_design", "message": m} for m in _design_errors(study.method, study.design, study.params)]
    if not issues:
        try:
            engine.calculate(study.method, engine_input(study, rows))
        except engine.DesignError as exc:
            issues = [i.as_dict() for i in exc.issues]
    planned = None
    d = study.design
    if family(study.method) in ("VARIABLE_GRR", "ATTRIBUTE"):
        per_op = d.get("parts_per_operator") if study.method == "GRR_NESTED_ANOVA" else d.get("parts")
        if d.get("operators") and per_op and d.get("trials"):
            planned = int(d["operators"]) * int(per_op) * int(d["trials"])
    return {"valid": not issues, "issues": issues, "observations": len(rows), "planned": planned}


def calculate(ctx: TenantContext, study_id: uuid.UUID) -> MsaRun:
    study = get_study(ctx, study_id, for_update=True)
    workflow.ensure_capability(ctx, ENTITY, study, "calculate")
    competency.ensure_authorized(ctx, ctx.user_id, "MSA_EVALUATION", plant_id=study.plant_id,
                                 gage_type_id=study.gage.gage_type_id)
    data = engine_input(study, _active_observations(ctx, study))
    _check_design(study.method, study.design, study.params)
    try:
        results = engine.calculate(study.method, data)
    except engine.DesignError as exc:
        raise BusinessRuleError("The study data do not form a valid design; nothing was calculated",
                                code="invalid_design", details=[i.as_dict() for i in exc.issues])
    criteria = resolve_criteria(ctx, study)
    evaluation, decision = evaluate(criteria, results)
    gage = study.gage
    number = (ctx.db.scalar(select(func.max(MsaRun.run_number)).where(MsaRun.study_id == study.id)) or 0) + 1
    run = MsaRun(
        organization_id=ctx.organization_id, study_id=study.id, run_number=number, method=study.method,
        algorithm_version=results["algorithm_version"], engine_version=results["engine_version"],
        validation_status=results["validation_status"], input_snapshot=data, input_hash=engine.input_hash(data),
        results=results, criteria_set_id=criteria.id if criteria else None,
        criteria_snapshot=criteria_snapshot(criteria) if criteria else None, evaluation=evaluation,
        decision=decision, calculated_by=ctx.user_id,
        gage_snapshot={"gage_code": gage.gage_code, "description": gage.description,
                       "status": gages.current_status(ctx, gage).value, "resolution": audit.plain(gage.resolution),
                       "last_calibration_date": audit.plain(gage.last_calibration_date),
                       "next_due_date": audit.plain(gage.next_due_date)},
    )
    ctx.db.add(run)
    ctx.db.flush()
    ctx.audit(action="msa.calculated", entity_type=ENTITY, entity_id=study.id,
              changes={"run": number, "method": study.method, "algorithm_version": run.algorithm_version,
                       "engine_version": run.engine_version, "decision": decision,
                       "criteria": f"{criteria.name} v{criteria.version}" if criteria else None,
                       "input_hash": run.input_hash})
    ctx.db.commit()
    return run


def get_run(ctx: TenantContext, run_id: uuid.UUID) -> MsaRun:
    run = ctx.db.scalar(select(MsaRun).where(MsaRun.id == run_id, MsaRun.organization_id == ctx.organization_id))
    if run is None:
        raise NotFoundError("Run not found")
    get_study(ctx, run.study_id)          # plant scope
    return run


def runs(ctx: TenantContext, study_id: uuid.UUID) -> list[MsaRun]:
    get_study(ctx, study_id)
    return list(ctx.db.scalars(select(MsaRun).where(MsaRun.study_id == study_id).order_by(MsaRun.run_number.desc())))


def latest_run(ctx: TenantContext, study: MsaStudy) -> MsaRun | None:
    return ctx.db.scalar(select(MsaRun).where(MsaRun.study_id == study.id).order_by(MsaRun.run_number.desc()).limit(1))


def verify_run(ctx: TenantContext, run_id: uuid.UUID) -> dict:
    """Recompute a stored run from its own input snapshot with the current engine.

    Nothing is written: the stored run stays exactly as it was produced.
    """
    run = get_run(ctx, run_id)
    current = engine.calculate(run.method, run.input_snapshot)
    stored_metrics, new_metrics = run.results.get("metrics", {}), current.get("metrics", {})
    diffs = {k: [stored_metrics.get(k), new_metrics.get(k)] for k in set(stored_metrics) | set(new_metrics)
             if not _same(stored_metrics.get(k), new_metrics.get(k))}
    return {"run_id": str(run.id), "stored_algorithm_version": run.algorithm_version,
            "stored_engine_version": run.engine_version, "current_algorithm_version": current["algorithm_version"],
            "current_engine_version": current["engine_version"],
            "input_hash_matches": engine.input_hash(run.input_snapshot) == run.input_hash,
            "identical": not diffs, "differences": diffs}


def _same(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= 1e-12 * max(1.0, abs(a), abs(b))
    return a == b


# ---------------------------------------------------------------- acceptance criteria

RULE_OPS = {"lte": lambda v, t: v <= t, "lt": lambda v, t: v < t, "gte": lambda v, t: v >= t,
            "gt": lambda v, t: v > t, "eq": lambda v, t: v == t}


def get_criteria(ctx: TenantContext, criteria_id: uuid.UUID, *, for_update: bool = False) -> MsaCriteriaSet:
    stmt = select(MsaCriteriaSet).where(MsaCriteriaSet.id == criteria_id,
                                        MsaCriteriaSet.organization_id == ctx.organization_id)
    c = ctx.db.scalar(stmt.with_for_update() if for_update else stmt)
    if c is None:
        raise NotFoundError("Criteria set not found")
    return c


def list_criteria(ctx: TenantContext, method: str | None, include_retired: bool) -> list[MsaCriteriaSet]:
    stmt = select(MsaCriteriaSet).where(MsaCriteriaSet.organization_id == ctx.organization_id)
    if method:
        stmt = stmt.where(MsaCriteriaSet.method == method)
    if not include_retired:
        stmt = stmt.where(MsaCriteriaSet.status != "RETIRED")
    return list(ctx.db.scalars(stmt.order_by(MsaCriteriaSet.name, MsaCriteriaSet.version.desc())))


def create_criteria(ctx: TenantContext, data: dict) -> MsaCriteriaSet:
    info = engine.method(data["method"])
    errors = []
    for i, r in enumerate(data["rules"], start=1):
        if r["metric"] not in info.metrics:
            errors.append(f"rule {i}: metric '{r['metric']}' is not produced by {info.code} "
                          f"(available: {list(info.metrics)})")
    if data["scope"] == "PLANT" and not data.get("plant_id"):
        errors.append("plant_id is required for PLANT scope")
    if data["scope"] == "CUSTOMER" and not data.get("customer"):
        errors.append("customer is required for CUSTOMER scope")
    if data["scope"] == "ORGANIZATION" and (data.get("plant_id") or data.get("customer")):
        errors.append("ORGANIZATION scope applies to the whole organization (no plant or customer)")
    if errors:
        raise BusinessRuleError("The acceptance criteria are not valid", code="invalid_criteria", details=errors)
    if data.get("plant_id"):
        get_plant(ctx, data["plant_id"])
    version = (ctx.db.scalar(select(func.max(MsaCriteriaSet.version)).where(
        MsaCriteriaSet.organization_id == ctx.organization_id, MsaCriteriaSet.name == data["name"])) or 0) + 1
    c = MsaCriteriaSet(organization_id=ctx.organization_id, version=version, status="DRAFT", created_by=ctx.user_id,
                       **data)
    ctx.db.add(c)
    ctx.db.flush()
    ctx.audit(action="msa.criteria_created", entity_type="msa_criteria", entity_id=c.id,
              changes={"name": c.name, "version": version, "method": c.method, "scope": c.scope, "rules": c.rules,
                       "source": c.source})
    ctx.db.commit()
    return c


def approve_criteria(ctx: TenantContext, criteria_id: uuid.UUID) -> MsaCriteriaSet:
    c = get_criteria(ctx, criteria_id, for_update=True)
    if c.status != "DRAFT":
        raise ConflictError("Only draft criteria can be approved", code="invalid_status")
    if c.created_by == ctx.user_id:
        raise BusinessRuleError("Criteria must be approved by a different user", code="segregation_of_duties")
    c.status, c.approved_by, c.approved_at = "APPROVED", ctx.user_id, datetime.now(UTC)
    ctx.audit(action="msa.criteria_approved", entity_type="msa_criteria", entity_id=c.id,
              changes={"name": c.name, "version": c.version})
    ctx.db.commit()
    return c


def retire_criteria(ctx: TenantContext, criteria_id: uuid.UUID, reason: str) -> MsaCriteriaSet:
    c = get_criteria(ctx, criteria_id, for_update=True)
    if c.status == "RETIRED":
        raise ConflictError("Already retired", code="invalid_status")
    c.status, c.retired_at, c.retired_reason = "RETIRED", datetime.now(UTC), reason
    ctx.audit(action="msa.criteria_retired", entity_type="msa_criteria", entity_id=c.id, reason=reason,
              changes={"name": c.name, "version": c.version})
    ctx.db.commit()
    return c


def resolve_criteria(ctx: TenantContext, study: MsaStudy) -> MsaCriteriaSet | None:
    """Explicit choice, else the most specific approved set: customer > plant > organization."""
    if study.criteria_set_id:
        c = get_criteria(ctx, study.criteria_set_id)
        return c if c.status == "APPROVED" else None
    candidates = list(ctx.db.scalars(select(MsaCriteriaSet).where(
        MsaCriteriaSet.organization_id == ctx.organization_id, MsaCriteriaSet.method == study.method,
        MsaCriteriaSet.status == "APPROVED")))

    def rank(c: MsaCriteriaSet):
        if c.scope == "CUSTOMER":
            ok = study.customer and c.customer and c.customer.strip().lower() == study.customer.strip().lower() \
                and (c.plant_id is None or c.plant_id == study.plant_id)
            return 3 if ok else None
        if c.scope == "PLANT":
            return 2 if c.plant_id == study.plant_id else None
        return 1

    ranked = [(rank(c), c.approved_at, c) for c in candidates if rank(c)]
    return max(ranked, key=lambda x: (x[0], x[1]))[2] if ranked else None


def criteria_snapshot(c: MsaCriteriaSet) -> dict:
    return {"id": str(c.id), "name": c.name, "version": c.version, "method": c.method, "scope": c.scope,
            "plant_id": audit.plain(c.plant_id), "customer": c.customer, "rules": c.rules, "source": c.source,
            "created_by": str(c.created_by), "approved_by": audit.plain(c.approved_by),
            "approved_at": audit.plain(c.approved_at)}


def evaluate(criteria: MsaCriteriaSet | None, results: dict) -> tuple[list[dict] | None, str]:
    """Compare results with the criteria. The statistical result never decides by itself:
    without criteria the decision is NO_CRITERIA; a metric that could not be computed
    makes the decision INCONCLUSIVE."""
    if results.get("validation_status") != "VALIDATED" or criteria is None:
        return None, "NO_CRITERIA"
    metrics = results.get("metrics", {})
    out, worst = [], "ACCEPTABLE"
    for r in criteria.rules:
        value = metrics.get(r["metric"])
        if value is None:
            status = "NOT_EVALUATED"
        else:
            target = r["value"]
            passed = RULE_OPS[r["op"]](value, target)
            status = "PASS" if passed else r.get("outcome", "NOT_ACCEPTABLE")
        out.append({"metric": r["metric"], "op": r["op"], "value": r["value"], "actual": value, "status": status,
                    "label": r.get("label")})
        if status == "NOT_EVALUATED" and worst != "NOT_ACCEPTABLE":
            worst = "INCONCLUSIVE"
        elif status == "NOT_ACCEPTABLE":
            worst = "NOT_ACCEPTABLE"
        elif status == "CONDITIONAL" and worst == "ACCEPTABLE":
            worst = "CONDITIONAL"
    return out, worst


# Starting points that an organization may adopt, edit and approve; never applied automatically.
CRITERIA_TEMPLATES = [
    {"name": "AIAG MSA 4th ed. - GRR (template)", "methods": ["GRR_CROSSED_AR", "GRR_CROSSED_ANOVA",
                                                              "GRR_NESTED_ANOVA"],
     "source": "AIAG MSA 4th ed., Table II-D 1, p. 78",
     "rules": [{"metric": "pct_sv_grr", "op": "lte", "value": 30, "outcome": "NOT_ACCEPTABLE", "label": "%GRR <= 30"},
               {"metric": "pct_sv_grr", "op": "lt", "value": 10, "outcome": "CONDITIONAL", "label": "%GRR < 10"},
               {"metric": "ndc", "op": "gte", "value": 5, "outcome": "NOT_ACCEPTABLE", "label": "ndc >= 5"}]},
    {"name": "AIAG MSA 4th ed. - Attribute (template)", "methods": ["ATTRIBUTE_AGREEMENT"],
     "source": "AIAG MSA 4th ed., Table III-C 6, p. 140",
     "rules": [{"metric": "min_effectiveness_pct", "op": "gte", "value": 80, "outcome": "NOT_ACCEPTABLE"},
               {"metric": "min_effectiveness_pct", "op": "gte", "value": 90, "outcome": "CONDITIONAL"},
               {"metric": "max_miss_rate_pct", "op": "lte", "value": 5, "outcome": "NOT_ACCEPTABLE"},
               {"metric": "max_miss_rate_pct", "op": "lte", "value": 2, "outcome": "CONDITIONAL"},
               {"metric": "max_false_alarm_rate_pct", "op": "lte", "value": 10, "outcome": "NOT_ACCEPTABLE"},
               {"metric": "max_false_alarm_rate_pct", "op": "lte", "value": 5, "outcome": "CONDITIONAL"},
               {"metric": "min_kappa_vs_reference", "op": "gt", "value": 0.75, "outcome": "CONDITIONAL"}]},
    {"name": "Statistical bias test (template)", "methods": ["BIAS"],
     "source": "AIAG MSA 4th ed., pp. 88-89",
     "rules": [{"metric": "bias_significant", "op": "eq", "value": False, "outcome": "NOT_ACCEPTABLE"}]},
    {"name": "Statistical linearity test (template)", "methods": ["LINEARITY"],
     "source": "AIAG MSA 4th ed., p. 98",
     "rules": [{"metric": "zero_line_within_bands", "op": "eq", "value": True, "outcome": "NOT_ACCEPTABLE"}]},
    {"name": "Stability without special causes (template)", "methods": ["STABILITY"],
     "source": "AIAG SPC 2nd ed., Table II.1, p. 75",
     "rules": [{"metric": "stable", "op": "eq", "value": True, "outcome": "NOT_ACCEPTABLE"}]},
    {"name": "Type 1 Cg/Cgk >= 1.33 (template)", "methods": ["TYPE1"],
     "source": "Bosch Booklet No. 10",
     "rules": [{"metric": "cg", "op": "gte", "value": 1.33, "outcome": "NOT_ACCEPTABLE"},
               {"metric": "cgk", "op": "gte", "value": 1.33, "outcome": "NOT_ACCEPTABLE"}]},
]


# ---------------------------------------------------------------- review, conclusion and workflow adapter

def set_conclusion(ctx: TenantContext, study_id: uuid.UUID, decision: str, comment: str | None) -> MsaStudy:
    study = get_study(ctx, study_id, for_update=True)
    workflow.ensure_capability(ctx, ENTITY, study, "conclude")
    if decision not in DECISIONS or decision == "NO_CRITERIA":
        raise BusinessRuleError("Invalid conclusion", code="invalid_decision")
    run = latest_run(ctx, study)
    if run is None:
        raise BusinessRuleError("The study has no calculation", code="no_results")
    if run.decision != decision and not (comment or "").strip():
        raise BusinessRuleError("A justification is required when the conclusion differs from the computed "
                                f"decision ({run.decision})", code="comment_required")
    before = {"final_decision": study.final_decision}
    study.final_decision, study.final_comment = decision, comment
    study.concluded_by, study.concluded_at = ctx.user_id, datetime.now(UTC)
    ctx.audit(action="msa.concluded", entity_type=ENTITY, entity_id=study.id, reason=comment,
              changes={"final_decision": [before["final_decision"], decision], "computed_decision": run.decision,
                       "run": run.run_number})
    ctx.db.commit()
    return study


def _facts(ctx: TenantContext, study: MsaStudy) -> dict:
    run = latest_run(ctx, study)
    metrics = (run.results.get("metrics") if run else None) or {}
    return {
        "has_run": run is not None,
        "decision": run.decision if run else None,
        "final_decision": study.final_decision,
        "method": study.method,
        "observation_count": len(_active_observations(ctx, study)),
        "has_report": bool(ctx.db.scalar(select(MsaReport.id).where(MsaReport.study_id == study.id).limit(1))),
        "has_customer": bool(study.customer),
        "pct_sv_grr": metrics.get("pct_sv_grr"),
        "ndc": metrics.get("ndc"),
        "cgk": metrics.get("cgk"),
        "min_kappa_vs_reference": metrics.get("min_kappa_vs_reference"),
    }


def _before_enter(ctx: TenantContext, study: MsaStudy, state: str) -> None:
    if state in ("IN_REVIEW", "APPROVED"):
        run = latest_run(ctx, study)
        if run is None:
            raise BusinessRuleError("Calculate the study before submitting it", code="no_results")
        current = engine.input_hash(engine_input(study, _active_observations(ctx, study)))
        if current != run.input_hash:
            raise BusinessRuleError("Data or configuration changed after the last calculation; recalculate",
                                    code="stale_results")
    if state == "APPROVED" and not study.final_decision:
        raise BusinessRuleError("Record the study conclusion before approving", code="conclusion_required")


def _after_enter(ctx: TenantContext, study: MsaStudy, from_state: str, to_state: str) -> None:
    if to_state == "APPROVED":
        if study.end_date is None:
            study.end_date = ctx.today()
        run = latest_run(ctx, study)
        events.emit(ctx.db, ctx.organization_id, "msa.study_completed", ENTITY, study.id,
                    {"study_code": study.study_code, "method": study.method, "gage_code": study.gage.gage_code,
                     "decision": study.final_decision, "computed_decision": run.decision,
                     "algorithm_version": run.algorithm_version, "run": run.run_number})
    notify(ctx, [study.responsible_id, study.created_by], "msa.status_changed",
           f"{study.study_code}: {from_state} -> {to_state}", study.title, f"/msa/{study.id}")


def _set_state(ctx: TenantContext, study: MsaStudy, state: str) -> None:
    study.status = state


DEFAULT_WORKFLOW = {
    "entity_type": ENTITY,
    "initial": "DRAFT",
    "states": [
        {"code": "DRAFT", "label": "Draft / data collection", "capabilities": ["configure", "capture", "calculate"]},
        {"code": "IN_REVIEW", "label": "In review", "capabilities": ["report", "conclude"]},
        {"code": "APPROVED", "label": "Approved", "capabilities": ["report"]},
        {"code": "CANCELLED", "label": "Cancelled", "capabilities": []},
    ],
    "transitions": [
        {"code": "SUBMIT", "label": "Submit for review", "from_states": ["DRAFT"], "to": "IN_REVIEW",
         "permission": P.MSA_MANAGE, "action": "ADVANCE"},
        {"code": "RETURN", "label": "Return for rework", "from_states": ["IN_REVIEW"], "to": "DRAFT",
         "permission": P.MSA_APPROVE, "action": "REJECT", "require_comment": True},
        {"code": "APPROVE", "label": "Approve study", "from_states": ["IN_REVIEW"], "to": "APPROVED",
         "permission": P.MSA_APPROVE, "action": "APPROVE", "segregate_from": ["responsible", "previous_actor"]},
        {"code": "CANCEL", "label": "Cancel study", "from_states": ["DRAFT", "IN_REVIEW"], "to": "CANCELLED",
         "permission": P.MSA_MANAGE, "action": "CANCEL", "require_comment": True},
    ],
    "escalations": [],
}


def _load(ctx: TenantContext, study_id: uuid.UUID, for_update: bool = False) -> MsaStudy:
    ctx.ensure(P.MSA_READ)
    return get_study(ctx, study_id, for_update=for_update)


# ---------------------------------------------------------------- reports

def _name(ctx: TenantContext, user_id) -> str | None:
    from app.modules.identity.models import User
    return ctx.db.scalar(select(User.full_name).where(User.id == user_id)) if user_id else None


def issue_report(ctx: TenantContext, study_id: uuid.UUID, run_id: uuid.UUID | None,
                 lang: str | None = None) -> MsaReport:
    from app.modules.documents import service as documents
    from app.modules.msa import guidance
    from app.modules.msa.report_pdf import render
    from app.modules.organizations.models import Department, Plant

    study = get_study(ctx, study_id, for_update=True)
    workflow.ensure_capability(ctx, ENTITY, study, "report")
    run = get_run(ctx, run_id) if run_id else latest_run(ctx, study)
    if run is None or run.study_id != study.id:
        raise BusinessRuleError("The study has no calculation to report", code="no_results")
    revision = (ctx.db.scalar(select(func.max(MsaReport.revision)).where(MsaReport.study_id == study.id)) or 0) + 1
    ops = sorted({o["operator"] for o in run.input_snapshot["observations"] if o.get("operator")})
    snap = {
        "organization": ctx.organization.name, "study_code": study.study_code, "revision": revision,
        "issued_on": ctx.today().isoformat(), "title": study.title, "method": run.method,
        "family": family(run.method), "characteristic": study.characteristic, "part_number": study.part_number,
        "part_revision": study.part_revision, "customer": study.customer,
        "plant": ctx.db.get(Plant, study.plant_id).name,
        "department": ctx.db.get(Department, study.department_id).name if study.department_id else None,
        "gage": run.gage_snapshot, "responsible": _name(ctx, study.responsible_id),
        "start_date": study.start_date.isoformat(), "end_date": audit.plain(study.end_date), "operators": ops,
        "run_number": run.run_number, "engine_version": run.engine_version, "algorithm_version": run.algorithm_version,
        "validation_status": run.validation_status, "input_hash": run.input_hash, "input": run.input_snapshot,
        "results": run.results, "criteria": run.criteria_snapshot, "evaluation": run.evaluation,
        "decision": run.decision, "final_decision": study.final_decision, "final_comment": study.final_comment,
        "concluded_by": _name(ctx, study.concluded_by), "calculated_by": _name(ctx, run.calculated_by),
        "calculated_at": run.calculated_at.isoformat(timespec="seconds"),
        "lang": lang or ctx.user.preferred_language or "es",
        "guidance": guidance.guidance(run.method, run.results), "guidance_version": guidance.GUIDANCE_VERSION,
    }
    pdf = render(snap)
    att = documents.store(ctx, entity_type=ENTITY, entity_id=study.id, category="REPORT",
                          filename=f"{study.study_code}-rev{revision}.pdf", data=pdf,
                          title=f"MSA report {study.study_code} rev {revision} (run #{run.run_number})",
                          locked=True, pdf_only=True)
    report = MsaReport(organization_id=ctx.organization_id, study_id=study.id, run_id=run.id, revision=revision,
                       attachment_id=att.id, issued_by=ctx.user_id)
    ctx.db.add(report)
    ctx.audit(action="msa.report_issued", entity_type=ENTITY, entity_id=study.id,
              changes={"revision": revision, "run": run.run_number, "document_id": str(att.id)})
    ctx.db.commit()
    return report


def reports(ctx: TenantContext, study_id: uuid.UUID) -> list[MsaReport]:
    get_study(ctx, study_id)
    return list(ctx.db.scalars(select(MsaReport).where(MsaReport.study_id == study_id)
                               .order_by(MsaReport.revision.desc())))
