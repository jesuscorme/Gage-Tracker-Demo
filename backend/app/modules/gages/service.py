"""Gage Management domain service.

All reads and writes go through here so that tenant scoping, plant scope, permissions
on sensitive fields and auditing are applied the same way everywhere.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, func, or_, select

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError, PermissionDeniedError
from app.modules.audit import service as audit
from app.modules.gages.models import Gage, GageStatusHistory, GageType
from app.modules.gages.schemas import (
    GageCreate,
    GageOut,
    GageTransitionIn,
    GageTypeIn,
    GageTypeUpdate,
    GageUpdate,
)
from app.modules.gages.status import (
    AVAILABLE_STATUSES,
    ControlStatus,
    GageStatus,
    effective_status,
    effective_status_sql,
    next_due,
    transition_permission,
)
from app.modules.identity.deps import TenantContext
from app.modules.identity.models import OrganizationMembership
from app.modules.identity.permissions import P
from app.modules.organizations.models import Department
from app.modules.organizations.router import get_plant

AUDITED_FIELDS = [
    "gage_code", "description", "gage_type_id", "plant_id", "department_id", "manufacturer", "model",
    "serial_number", "range_min", "range_max", "unit", "resolution", "accuracy", "criticality",
    "location", "responsible_user_id", "calibration_frequency_days", "last_calibration_date",
    "next_due_date", "notes",
]
# Changing these moves the due date, so they can turn an overdue gage back into a usable one.
DUE_DATE_FIELDS = {"calibration_frequency_days", "last_calibration_date"}
REQUIRED_FIELDS = {"description", "gage_type_id", "plant_id", "calibration_frequency_days"}
SORTS = {
    "gage_code": Gage.gage_code,
    "description": Gage.description,
    "next_due_date": Gage.next_due_date,
    "updated_at": Gage.updated_at,
}


# ---------------------------------------------------------------- gage types


def get_gage_type(ctx: TenantContext, type_id: uuid.UUID) -> GageType:
    gt = ctx.db.scalar(
        select(GageType).where(GageType.id == type_id, GageType.organization_id == ctx.organization_id)
    )
    if gt is None:
        raise NotFoundError("Gage type not found")
    return gt


def list_gage_types(ctx: TenantContext, include_inactive: bool) -> list[GageType]:
    stmt = select(GageType).where(GageType.organization_id == ctx.organization_id)
    if not include_inactive:
        stmt = stmt.where(GageType.is_active.is_(True))
    return list(ctx.db.scalars(stmt.order_by(GageType.name)))


def create_gage_type(ctx: TenantContext, body: GageTypeIn) -> GageType:
    code = body.code.strip().upper()
    exists = ctx.db.scalar(
        select(GageType.id).where(GageType.organization_id == ctx.organization_id, GageType.code == code)
    )
    if exists:
        raise ConflictError("A gage type with this code already exists", code="duplicate_gage_type")
    gt = GageType(organization_id=ctx.organization_id, **body.model_dump(exclude={"code"}), code=code)
    ctx.db.add(gt)
    ctx.db.flush()
    ctx.audit(action="gage_type.created", entity_type="gage_type", entity_id=gt.id,
              changes=body.model_dump(mode="json") | {"code": code})
    ctx.db.commit()
    return gt


def update_gage_type(ctx: TenantContext, type_id: uuid.UUID, body: GageTypeUpdate) -> GageType:
    gt = get_gage_type(ctx, type_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("name") is None:
        data.pop("name", None)
    if data.get("is_active") is None:
        data.pop("is_active", None)
    before = audit.snapshot(gt, list(data))
    for k, v in data.items():
        setattr(gt, k, v)
    changes = audit.diff(before, data)
    if changes:
        ctx.audit(action="gage_type.updated", entity_type="gage_type", entity_id=gt.id, changes=changes)
    ctx.db.commit()
    return gt


# ---------------------------------------------------------------- reads


def scoped_query(ctx: TenantContext) -> Select:
    stmt = select(Gage).where(Gage.organization_id == ctx.organization_id)
    if ctx.plant_ids is not None:
        stmt = stmt.where(Gage.plant_id.in_(ctx.plant_ids))
    return stmt


def _status_sql(ctx: TenantContext):
    return effective_status_sql(Gage.control_status, Gage.next_due_date, ctx.today(), ctx.organization.due_soon_days)


def to_out(ctx: TenantContext, g: Gage) -> GageOut:
    status = effective_status(g.control_status, g.next_due_date, ctx.today(), ctx.organization.due_soon_days)
    return GageOut(
        id=g.id,
        gage_code=g.gage_code,
        description=g.description,
        gage_type=g.gage_type,
        plant=g.plant,
        department=g.department,
        responsible=g.responsible,
        manufacturer=g.manufacturer,
        model=g.model,
        serial_number=g.serial_number,
        range_min=g.range_min,
        range_max=g.range_max,
        unit=g.unit,
        resolution=g.resolution,
        accuracy=g.accuracy,
        criticality=g.criticality,
        location=g.location,
        notes=g.notes,
        calibration_frequency_days=g.calibration_frequency_days,
        last_calibration_date=g.last_calibration_date,
        next_due_date=g.next_due_date,
        days_to_due=(g.next_due_date - ctx.today()).days if g.next_due_date else None,
        control_status=g.control_status,
        status=status,
        available_for_use=status in AVAILABLE_STATUSES,
        retired_at=g.retired_at,
        created_at=g.created_at,
        updated_at=g.updated_at,
    )


def get_gage(ctx: TenantContext, gage_id: uuid.UUID, *, for_update: bool = False) -> Gage:
    stmt = scoped_query(ctx).where(Gage.id == gage_id)
    if for_update:
        stmt = stmt.with_for_update(of=Gage)
    gage = ctx.db.scalar(stmt)
    if gage is None:
        raise NotFoundError("Gage not found")
    return gage


def list_gages(
    ctx: TenantContext,
    *,
    q: str | None,
    statuses: list[GageStatus] | None,
    plant_id: uuid.UUID | None,
    department_id: uuid.UUID | None,
    gage_type_id: uuid.UUID | None,
    available: bool | None,
    include_inactive: bool,
    sort: str,
    page: int,
    page_size: int,
) -> tuple[list[Gage], int]:
    stmt = scoped_query(ctx)
    status_col = _status_sql(ctx)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Gage.gage_code.ilike(like), Gage.description.ilike(like), Gage.serial_number.ilike(like),
                Gage.manufacturer.ilike(like), Gage.model.ilike(like), Gage.location.ilike(like),
            )
        )
    if statuses:
        stmt = stmt.where(status_col.in_([s.value for s in statuses]))
    elif not include_inactive:
        stmt = stmt.where(Gage.control_status != ControlStatus.INACTIVE.value)
    if available is not None:
        avail = status_col.in_([s.value for s in AVAILABLE_STATUSES])
        stmt = stmt.where(avail if available else ~avail)
    for col, value in ((Gage.plant_id, plant_id), (Gage.department_id, department_id),
                       (Gage.gage_type_id, gage_type_id)):
        if value is not None:
            stmt = stmt.where(col == value)

    total = ctx.db.scalar(select(func.count()).select_from(stmt.with_only_columns(Gage.id).subquery()))
    key = sort.lstrip("-")
    if key not in SORTS:
        raise BusinessRuleError("Unsupported sort field", code="invalid_sort", details={"allowed": list(SORTS)})
    order = SORTS[key].desc().nulls_last() if sort.startswith("-") else SORTS[key].asc().nulls_first()
    rows = ctx.db.scalars(stmt.order_by(order, Gage.gage_code).limit(page_size).offset((page - 1) * page_size))
    return list(rows.unique()), total


def status_counts(ctx: TenantContext) -> dict[str, int]:
    status_col = _status_sql(ctx).label("status")
    stmt = scoped_query(ctx).with_only_columns(status_col, func.count()).group_by(status_col)
    counts = {s.value: 0 for s in GageStatus}
    counts.update({status: n for status, n in ctx.db.execute(stmt)})
    return counts


# ---------------------------------------------------------------- writes


def _validate_refs(ctx: TenantContext, data: dict, gage: Gage | None) -> None:
    """Check that every referenced entity belongs to the tenant and is consistent."""
    plant_id = data.get("plant_id", gage.plant_id if gage else None)
    if "plant_id" in data:
        get_plant(ctx, data["plant_id"])  # 404 if outside tenant or user's plant scope
    if "gage_type_id" in data:
        gt = get_gage_type(ctx, data["gage_type_id"])
        if not gt.is_active and (gage is None or gage.gage_type_id != gt.id):
            raise BusinessRuleError("Gage type is inactive", code="gage_type_inactive")

    department_id = data.get("department_id", gage.department_id if gage else None)
    if department_id is not None and ("department_id" in data or "plant_id" in data):
        dept = ctx.db.scalar(
            select(Department).where(
                Department.id == department_id, Department.organization_id == ctx.organization_id
            )
        )
        if dept is None:
            raise NotFoundError("Department not found")
        if dept.plant_id != plant_id:
            raise BusinessRuleError("Department does not belong to the selected plant",
                                    code="department_plant_mismatch")

    if data.get("responsible_user_id") is not None:
        member = ctx.db.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.user_id == data["responsible_user_id"],
                OrganizationMembership.organization_id == ctx.organization_id,
                OrganizationMembership.is_active.is_(True),
            )
        )
        if member is None:
            raise BusinessRuleError("Responsible user is not an active member of the organization",
                                    code="invalid_responsible")

    last_cal = data.get("last_calibration_date")
    if last_cal is not None and last_cal > ctx.today():
        raise BusinessRuleError("Calibration date cannot be in the future", code="future_calibration_date")


def create_gage(ctx: TenantContext, body: GageCreate) -> Gage:
    data = body.model_dump()
    data["gage_code"] = body.gage_code.strip().upper()
    _validate_refs(ctx, data, None)

    if data["calibration_frequency_days"] is None:
        gt = get_gage_type(ctx, body.gage_type_id)
        if gt.default_frequency_days is None:
            raise BusinessRuleError("Calibration frequency is required", code="frequency_required")
        data["calibration_frequency_days"] = gt.default_frequency_days

    if ctx.db.scalar(
        select(Gage.id).where(Gage.organization_id == ctx.organization_id, Gage.gage_code == data["gage_code"])
    ):
        raise ConflictError("Gage ID already exists in this organization", code="duplicate_gage_code")

    gage = Gage(
        organization_id=ctx.organization_id,
        control_status=ControlStatus.ACTIVE.value,
        created_by=ctx.user_id,
        updated_by=ctx.user_id,
        **data,
    )
    gage.next_due_date = next_due(gage.last_calibration_date, gage.calibration_frequency_days)
    ctx.db.add(gage)
    ctx.db.flush()

    status = effective_status(gage.control_status, gage.next_due_date, ctx.today(), ctx.organization.due_soon_days)
    ctx.db.add(GageStatusHistory(
        organization_id=ctx.organization_id, gage_id=gage.id, to_control_status=gage.control_status,
        to_status=status.value, reason="Gage registered", changed_by=ctx.user_id,
    ))
    ctx.audit(action="gage.created", entity_type="gage", entity_id=gage.id,
              changes=audit.snapshot(gage, AUDITED_FIELDS))
    ctx.db.commit()
    return get_gage(ctx, gage.id)


def update_gage(ctx: TenantContext, gage_id: uuid.UUID, body: GageUpdate) -> Gage:
    gage = get_gage(ctx, gage_id, for_update=True)
    if gage.control_status == ControlStatus.INACTIVE:
        raise ConflictError("Retired gages cannot be edited; reactivate it first", code="gage_inactive")

    data = body.model_dump(exclude_unset=True)
    nulled = sorted(k for k in REQUIRED_FIELDS if k in data and data[k] is None)
    if nulled:
        raise BusinessRuleError("Required fields cannot be empty", code="required_field", details=nulled)

    # Only change what actually differs, so re-sending an unchanged form is harmless.
    data = {k: v for k, v in data.items() if audit.plain(getattr(gage, k)) != audit.plain(v)}
    if DUE_DATE_FIELDS & data.keys() and not ctx.has(P.GAGES_RELEASE):
        raise PermissionDeniedError(
            "Changing calibration date or frequency requires release authorization",
            details={"required_permission": P.GAGES_RELEASE, "fields": sorted(DUE_DATE_FIELDS & data.keys())},
        )
    if "plant_id" in data:
        get_plant(ctx, gage.plant_id)  # must also be allowed on the plant it leaves
        if "department_id" not in data:
            data["department_id"] = None
    if not data:
        return gage

    _validate_refs(ctx, data, gage)
    rmin = data.get("range_min", gage.range_min)
    rmax = data.get("range_max", gage.range_max)
    if rmin is not None and rmax is not None and rmin > rmax:
        raise BusinessRuleError("range_min must be less than or equal to range_max", code="invalid_range")

    before = audit.snapshot(gage, AUDITED_FIELDS)
    status_before = effective_status(gage.control_status, gage.next_due_date, ctx.today(),
                                     ctx.organization.due_soon_days)
    for k, v in data.items():
        setattr(gage, k, v)
    gage.next_due_date = next_due(gage.last_calibration_date, gage.calibration_frequency_days)
    gage.updated_by = ctx.user_id

    changes = audit.diff(before, audit.snapshot(gage, AUDITED_FIELDS))
    status_after = effective_status(gage.control_status, gage.next_due_date, ctx.today(),
                                    ctx.organization.due_soon_days)
    if status_after != status_before:
        changes["status"] = [status_before.value, status_after.value]
    ctx.audit(action="gage.updated", entity_type="gage", entity_id=gage.id, changes=changes)
    ctx.db.commit()
    return get_gage(ctx, gage.id)


def transition_gage(ctx: TenantContext, gage_id: uuid.UUID, body: GageTransitionIn) -> Gage:
    gage = get_gage(ctx, gage_id, for_update=True)
    current = ControlStatus(gage.control_status)
    target = body.target
    permission = transition_permission(current, target)
    if permission is None:
        raise BusinessRuleError(
            f"Transition {current.value} -> {target.value} is not allowed",
            code="invalid_transition",
            details={"from": current.value, "to": target.value},
        )
    ctx.ensure(permission)

    if body.calibration_date is not None:
        if not (current == ControlStatus.IN_CALIBRATION and target == ControlStatus.ACTIVE):
            raise BusinessRuleError("A calibration date can only be recorded when releasing from calibration",
                                    code="calibration_date_not_allowed")
        if body.calibration_date > ctx.today():
            raise BusinessRuleError("Calibration date cannot be in the future", code="future_calibration_date")
        if gage.last_calibration_date and body.calibration_date < gage.last_calibration_date:
            raise BusinessRuleError("Calibration date is earlier than the last recorded calibration",
                                    code="calibration_date_regression")

    window = ctx.organization.due_soon_days
    status_before = effective_status(gage.control_status, gage.next_due_date, ctx.today(), window)
    before = audit.snapshot(gage, ["control_status", "last_calibration_date", "next_due_date"])

    gage.control_status = target.value
    if body.calibration_date is not None:
        gage.last_calibration_date = body.calibration_date
        gage.next_due_date = next_due(body.calibration_date, gage.calibration_frequency_days)
    gage.retired_at = datetime.now(UTC) if target == ControlStatus.INACTIVE else None
    gage.updated_by = ctx.user_id

    status_after = effective_status(gage.control_status, gage.next_due_date, ctx.today(), window)
    ctx.db.add(GageStatusHistory(
        organization_id=ctx.organization_id, gage_id=gage.id,
        from_control_status=current.value, to_control_status=target.value,
        from_status=status_before.value, to_status=status_after.value,
        reason=body.reason.strip(), changed_by=ctx.user_id,
    ))
    action = {
        ControlStatus.INACTIVE: "gage.retired",
        ControlStatus.ACTIVE: "gage.reactivated" if current == ControlStatus.INACTIVE else "gage.released",
    }.get(target, "gage.restricted")
    changes = audit.diff(before, audit.snapshot(gage, ["control_status", "last_calibration_date", "next_due_date"]))
    changes["status"] = [status_before.value, status_after.value]
    ctx.audit(action=action, entity_type="gage", entity_id=gage.id, changes=changes, reason=body.reason.strip())
    ctx.db.commit()
    return get_gage(ctx, gage.id)


def status_history(ctx: TenantContext, gage_id: uuid.UUID) -> list[GageStatusHistory]:
    get_gage(ctx, gage_id)
    return list(ctx.db.scalars(
        select(GageStatusHistory)
        .where(GageStatusHistory.gage_id == gage_id, GageStatusHistory.organization_id == ctx.organization_id)
        .order_by(GageStatusHistory.changed_at.desc(), GageStatusHistory.id)
    ))
